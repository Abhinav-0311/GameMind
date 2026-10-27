import time
import copy
import logging
import traceback
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterator
from uuid import UUID

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from app.design_agent.contracts import (
    DesignAgentState,
    ResearchPlan,
    ResumeDecision,
)
from app.design_agent.grounding import (
    complete_design_critique,
    ground_blueprint_citations,
    validate_generated_blueprint,
    validate_structured_revision,
    review_targets,
    memory_is_unspecified,
    NoMaterialRevisionError,
    OFFLINE_REVISION_UNAVAILABLE,
)
from app.design_agent.provider import (
    DesignAgentProvider,
    MockDesignAgentProvider,
    ProviderResult,
)
from app.design_agent.llm_provider import NvidiaProviderError, NvidiaStructuredOutputError, NvidiaTruncatedOutputError
from app.config import settings
from app.design_agent.finding_reviews import content_digest
from app.design_agent.review_policy import canonical_review_request, requires_design_quality_review, saved_review_request, validate_persisted_design_approval, require_degraded_acknowledgement
from app.models.blueprint import GameBlueprint
from app.models.design_agent import (
    DesignAgentArtifact,
    DesignAgentCritique,
    DesignAgentEvidenceSnapshot,
    DesignAgentJob,
    DesignAgentNodeExecution,
    DesignAgentReviewEvent,
    DesignAgentRun,
)
from app.models.document import Document
from app.models.design_decision import DesignDecision
from app.services.rag_service import RAGService


logger = logging.getLogger(__name__)


class FinalizationIntegrityError(ValueError):
    """A final candidate must not silently change the reviewed draft."""


class DesignAgentWorkflow:
    """Durable LangGraph workflow whose node side effects are restart-safe."""

    def __init__(
        self,
        database_url: str,
        session_factory: sessionmaker,
        provider: DesignAgentProvider | None = None,
        rag_service: RAGService | None = None,
    ):
        self.database_url = database_url.replace("postgresql+psycopg2://", "postgresql://")
        self.session_factory = session_factory
        self.provider = provider or MockDesignAgentProvider()
        self.rag_service = rag_service or RAGService()

    @staticmethod
    def _thread_config(run_id: UUID | str) -> dict[str, Any]:
        return {"configurable": {"thread_id": f"design-agent:{run_id}"}}

    @contextmanager
    def _checkpointer(self) -> Iterator[PostgresSaver]:
        # Checkpoint tables are created by Alembic, so setup() is intentionally
        # not called here.
        with PostgresSaver.from_conn_string(self.database_url) as saver:
            yield saver

    def _compile(self, saver: PostgresSaver):
        graph = StateGraph(DesignAgentState)
        graph.add_node("plan", self._plan)
        graph.add_node("retrieve_evidence", self._retrieve_evidence)
        graph.add_node("generate_blueprint", self._generate_blueprint)
        graph.add_node("critique", self._critique)
        graph.add_node("human_review", self._human_review)
        graph.add_node("revise", self._revise)
        graph.add_node("revision_limit", self._revision_limit)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "plan")
        graph.add_edge("plan", "retrieve_evidence")
        graph.add_edge("retrieve_evidence", "generate_blueprint")
        graph.add_edge("generate_blueprint", "critique")
        graph.add_edge("critique", "human_review")
        graph.add_conditional_edges(
            "human_review",
            self._route_after_review,
            {
                "approve": "finalize",
                "reject": "revise",
                "revision_limit": "revision_limit",
            },
        )
        graph.add_conditional_edges("revise", lambda state: "human_review" if state.get("revision_failed") else "critique")
        graph.add_edge("revision_limit", END)
        graph.add_conditional_edges("finalize", lambda state: "human_review" if state.get("finalization_failed") else END)
        return graph.compile(checkpointer=saver)

    def start(self, run: DesignAgentRun) -> dict[str, Any]:
        initial_state: DesignAgentState = {
            "run_id": str(run.id),
            "game_project_id": run.game_project_id,
            "objective": run.objective,
            "document_ids": [str(document_id) for document_id in run.document_ids],
            "max_revisions": run.max_revisions,
            "revision_count": run.revision_count,
            "fresh_dialogue": bool((run.model_config or {}).get("fresh_dialogue")),
            "dialogue_policy": (run.model_config or {}).get("dialogue_policy"),
            "defer_runtime": (run.model_config or {}).get("defer_runtime") is True,
            "allow_unspecified_memory": (run.model_config or {}).get("allow_unspecified_memory") is True,
            "design_contract_version": (run.model_config or {}).get("design_contract_version", 1),
        }
        with self._checkpointer() as saver:
            return self._compile(saver).invoke(initial_state, self._thread_config(run.id))

    def resume(self, run_id: UUID, decision: ResumeDecision) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            with self._checkpointer() as saver:
                return self._compile(saver).invoke(
                    Command(resume=decision.model_dump()),
                    self._thread_config(run_id),
                )
        except Exception as error:
            messages = [f"{type(error).__name__}: {error}", traceback.format_exc()]
            # Traceback formatting omits locals; redact configured credentials in exception text too.
            for name in type(settings).model_fields:
                value = getattr(settings, name)
                if (isinstance(value, str) and len(value) >= 4
                        and (name == "DATABASE_URL" or any(part in name for part in ("KEY", "SECRET", "PASSWORD", "TOKEN")))):
                    messages = [message.replace(value, "[REDACTED]") for message in messages]
            logger.error("Design-agent resume failed for run %s\n%s", run_id, messages[1])
            with self._session() as db:
                run = db.get(DesignAgentRun, run_id)
                if run and run.current_node == "human_review":
                    execution = db.query(DesignAgentNodeExecution).filter_by(
                        run_id=run.id, game_project_id=run.game_project_id,
                        node_name="human_review", status="waiting").order_by(
                        DesignAgentNodeExecution.attempt.desc()).first()
                    if execution is None:
                        execution = self._begin_execution(db, run, "human_review")
                    self._fail_execution(db, run, execution, started, RuntimeError(messages[0]))
                    execution.details = {**(execution.details or {}), "http_status": 500}
                    db.commit()
            raise

    @contextmanager
    def _session(self) -> Iterator[Session]:
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()

    def retry_critique(self, run_id: UUID, artifact_id: UUID, failed_execution_id: UUID,
                       job_id: UUID, worker_id: str) -> dict[str, Any]:
        with self._checkpointer() as saver:
            graph, config = self._compile(saver), self._thread_config(run_id)
            checkpoint = graph.get_state(config)
            state = checkpoint.values
            with self._session() as db:
                run = db.get(DesignAgentRun, run_id)
                artifact = db.query(DesignAgentArtifact).filter_by(run_id=run_id).order_by(DesignAgentArtifact.version.desc()).first()
                failed = db.query(DesignAgentNodeExecution).filter_by(run_id=run_id, node_name="critique").order_by(
                    DesignAgentNodeExecution.attempt.desc()).first()
                snapshot = db.get(DesignAgentEvidenceSnapshot, artifact.evidence_snapshot_id) if artifact else None
                job = db.get(DesignAgentJob, job_id)
                if (not run or run.status != "review_queued" or run.current_node != "critique"
                        or self.provider.name != run.provider_name or not job or not worker_id
                        or job.status != "running" or job.locked_by != worker_id or job.run_id != run.id
                        or job.operation != "retry_critique" or job.game_project_id != run.game_project_id
                        or job.payload.get("artifact_id") != str(artifact_id)
                        or job.payload.get("failed_execution_id") != str(failed_execution_id)
                        or (self.provider.name in {"nvidia", "gemini"} and job.payload.get("hosted_provider_consent") is not True)
                        or (self.provider.name in {"nvidia", "gemini"} and ((run.model_config or {}).get("hosted_provider_consent") is not True
                            or set((run.model_config or {}).get("consented_document_ids", [])) != set(run.document_ids)))
                        or not artifact or artifact.id != artifact_id or artifact.immutable
                        or not failed or failed.id != failed_execution_id or failed.status != "failed"
                        or checkpoint.next != ("critique",) or not snapshot or not snapshot.items
                        or artifact.game_project_id != run.game_project_id or snapshot.game_project_id != run.game_project_id
                        or snapshot.run_id != run.id or state.get("game_project_id") != run.game_project_id
                        or state.get("run_id") != str(run.id) or state.get("document_ids") != run.document_ids
                        or state.get("current_artifact_id") != str(artifact.id)
                        or state.get("current_artifact_version") != artifact.version
                        or state.get("current_artifact") != artifact.content
                        or state.get("evidence_snapshot_id") != str(snapshot.id)
                        or state.get("evidence_items") != snapshot.items
                        or canonical_review_request(state) != saved_review_request(run)):
                    raise ValueError("The saved draft, evidence, provider or retry owner is unavailable or stale; no retry was sent.")
            return graph.invoke(None, config)

    @staticmethod
    def _load_run(db: Session, state: DesignAgentState) -> DesignAgentRun:
        run = db.query(DesignAgentRun).filter(
            DesignAgentRun.id == UUID(state["run_id"]),
            DesignAgentRun.game_project_id == state["game_project_id"],
        ).first()
        if run is None:
            raise RuntimeError("Design-agent run no longer exists in the active project.")
        return run

    @staticmethod
    def _begin_execution(
        db: Session,
        run: DesignAgentRun,
        node_name: str,
        *,
        status: str = "running",
        provider_name: str | None = None,
        model_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> DesignAgentNodeExecution:
        latest_attempt = db.query(func.max(DesignAgentNodeExecution.attempt)).filter(
            DesignAgentNodeExecution.run_id == run.id,
            DesignAgentNodeExecution.node_name == node_name,
        ).scalar()
        execution = DesignAgentNodeExecution(
            run_id=run.id,
            game_project_id=run.game_project_id,
            node_name=node_name,
            attempt=(latest_attempt or 0) + 1,
            status=status,
            provider_name=provider_name,
            model_name=model_name,
            details=details or {},
        )
        run.current_node = node_name
        if status != "waiting":
            run.status = "running"
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    @staticmethod
    def _complete_execution(
        db: Session,
        execution: DesignAgentNodeExecution,
        started: float,
        *,
        result: ProviderResult | None = None,
        status: str = "completed",
        details: dict[str, Any] | None = None,
    ) -> None:
        execution.status = status
        execution.latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        execution.completed_at = datetime.now(timezone.utc)
        if result:
            execution.provider_name = result.provider_name or execution.provider_name or "unknown"
            execution.model_name = result.model_name
            execution.input_tokens = result.usage.input_tokens
            execution.output_tokens = result.usage.output_tokens
            execution.cost_usd = Decimal(str(result.usage.cost_usd))
        if details is not None:
            execution.details = details
        db.commit()

    @staticmethod
    def _fail_execution(
        db: Session,
        run: DesignAgentRun,
        execution: DesignAgentNodeExecution,
        started: float,
        error: Exception,
        *, result: ProviderResult | None = None,
    ) -> None:
        execution.status = "failed"
        execution.error = str(error)
        execution.input_tokens = 0
        execution.output_tokens = 0
        execution.details = {**(execution.details or {}), "cost_status": "unavailable",
                             "token_usage_scope": "unavailable"}
        if isinstance(error, NvidiaProviderError):
            if error.diagnostics.get("degraded"):
                run.model_config = {**(run.model_config or {}), "degraded": True}
            execution.details = {
                **(execution.details or {}),
                "failure_code": error.code,
                "request_attempts": error.attempts,
                "provider_diagnostics": error.diagnostics,
            }
            execution.model_name = error.diagnostics.get("model_name") or execution.model_name
            completions = error.diagnostics.get("completions") or []
            # These are disjoint records: a successful truncation retry is
            # already combined into one diagnostic; two failed responses are
            # recorded separately. Do not add an aggregate on top or dedupe
            # equal usage values from different requests.
            for completion in completions:
                if not isinstance(completion, dict):
                    continue
                for field in ("input_tokens", "output_tokens"):
                    value = completion.get(field)
                    if type(value) is int and value >= 0:
                        setattr(execution, field, getattr(execution, field) + value)
                        execution.details["token_usage_scope"] = "completed_responses_only"
        if result is not None:
            # Provider success followed by a grounding/persistence failure
            # still consumed tokens. The returned usage is already aggregated.
            execution.input_tokens = result.usage.input_tokens
            execution.output_tokens = result.usage.output_tokens
            execution.provider_name = result.provider_name or execution.provider_name or "unknown"
            execution.model_name = result.model_name
            execution.cost_usd = Decimal(str(result.usage.cost_usd))
            execution.details.update(cost_status=result.metadata.get("cost_status", "unavailable"),
                                     token_usage_scope="completed_responses_only")
            if result.metadata.get("degraded"):
                run.model_config = {**(run.model_config or {}), "degraded": True}
                execution.details.update(degraded=True, fallback_to=result.metadata.get("fallback_to"))
        if execution.node_name == "revise" and isinstance(error, NoMaterialRevisionError) and run.provider_name == "mock":
            error = NoMaterialRevisionError(OFFLINE_REVISION_UNAVAILABLE)
            execution.error = str(error)
            execution.details["http_status"] = 409
        elif (execution.node_name in {"plan", "generate_blueprint", "critique", "revise"}
                and (isinstance(error, (ValueError, NvidiaStructuredOutputError, NvidiaTruncatedOutputError))
                     or isinstance(error, NvidiaProviderError) and error.code == "invalid_response_envelope")):
            execution.details["http_status"] = 502
        elif isinstance(error, NvidiaProviderError) and error.code in {"provider_unavailable", "provider_timeout"}:
            execution.details["http_status"] = 503
        execution.latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        execution.completed_at = datetime.now(timezone.utc)
        run.status = "failed"
        run.last_error = str(error)
        db.commit()

    def _provider_node(
        self,
        state: DesignAgentState,
        node_name: str,
        call: Callable[[], ProviderResult],
        persist: Callable[[Session, DesignAgentRun, ProviderResult], dict[str, Any]],
    ) -> dict[str, Any]:
        with self._session() as db:
            run = self._load_run(db, state)
            if (node_name == "revise" and (run.model_config or {}).get("consecutive_revision_failures", 0)
                    >= settings.DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES):
                run.last_error = "Consecutive failed revision limit reached. No further revision request was sent; start a new run with fresh consent."
                db.commit()
                return {"revision_failed": True, "revision_count": run.revision_count}
            execution = self._begin_execution(
                db,
                run,
                node_name,
                provider_name=self.provider.name,
            )
            started = time.perf_counter()
            result = None
            try:
                primary = getattr(self.provider, "primary", self.provider)
                transport = getattr(primary, "llm_provider", None)
                request_context = getattr(transport, "run_context", None)
                with request_context(run.id) if request_context else nullcontext():
                    result = call()
                update = persist(db, run, result)
                degraded = bool(result.metadata.get("degraded"))
                if degraded:
                    run.model_config = {
                        **(run.model_config or {}),
                        "degraded": True,
                    }
                    db.commit()
                self._complete_execution(
                    db,
                    execution,
                    started,
                    result=result,
                    status="degraded" if degraded else "completed",
                    details={
                        "output_keys": sorted(update.keys()),
                        **({"artifact_id": update["current_artifact_id"]} if update.get("current_artifact_id") else {}),
                        **result.metadata,
                    },
                )
                return update
            except Exception as error:
                db.rollback()
                execution = db.get(DesignAgentNodeExecution, execution.id)
                run = db.get(DesignAgentRun, run.id)
                self._fail_execution(db, run, execution, started, error, result=result)
                saved_revision = db.query(DesignAgentArtifact.id).filter(
                    DesignAgentArtifact.run_id == run.id,
                    DesignAgentArtifact.version > state.get("current_artifact_version", 0)).first() if node_name == "revise" else None
                if node_name == "revise" and state.get("critique_id") and saved_revision is None:
                    # A rejected candidate is not a new draft; retain reviewable work without retrying automatically.
                    failures = (run.model_config or {}).get("consecutive_revision_failures", 0) + 1
                    run.model_config = {**(run.model_config or {}), "consecutive_revision_failures": failures}
                    db.commit()
                    return {"revision_failed": True, "revision_count": run.revision_count}
                raise

    def _plan(self, state: DesignAgentState) -> dict[str, Any]:
        def persist(db: Session, run: DesignAgentRun, result: ProviderResult) -> dict[str, Any]:
            plan = ResearchPlan.model_validate(result.content)
            run.model_config = {
                **(run.model_config or {}),
                "plan_model": result.model_name,
            }
            db.commit()
            return {"plan": plan.model_dump()}

        return self._provider_node(
            state,
            "plan",
            lambda: self.provider.plan(state["objective"], state["document_ids"]),
            persist,
        )

    def _retrieve_evidence(self, state: DesignAgentState) -> dict[str, Any]:
        with self._session() as db:
            run = self._load_run(db, state)
            existing = db.query(DesignAgentEvidenceSnapshot).filter(
                DesignAgentEvidenceSnapshot.run_id == run.id,
                DesignAgentEvidenceSnapshot.revision == 1,
            ).first()
            execution = self._begin_execution(
                db,
                run,
                "retrieve_evidence",
                provider_name="local_retrieval",
                model_name="chroma-local-lexical-v1",
            )
            started = time.perf_counter()
            try:
                if existing:
                    resolved_decisions = (run.model_config or {}).get(
                        "resolved_decisions", []
                    )
                    self._complete_execution(
                        db,
                        execution,
                        started,
                        details={
                            "evidence_snapshot_id": str(existing.id),
                            "resolved_decision_count": len(resolved_decisions),
                            "resolved_decision_ids": [
                                item.get("decision_id")
                                for item in resolved_decisions
                                if item.get("decision_id")
                            ],
                            "reused": True,
                        },
                    )
                    return {
                        "evidence_snapshot_id": str(existing.id),
                        "evidence_items": existing.items,
                        "resolved_decisions": resolved_decisions,
                    }

                plan = ResearchPlan.model_validate(state["plan"])
                evidence = self.rag_service.query_lore_sections(
                    plan.section_queries,
                    limit_per_section=3,
                    game_project_id=run.game_project_id,
                    document_ids=state["document_ids"],
                )
                resolved_decisions = [
                    {
                        "decision_id": str(decision.id),
                        "document_id": str(decision.document_id),
                        "title": decision.title,
                        "guidance": decision.guidance,
                        "decision": decision.decision.strip(),
                    }
                    for decision in db.query(DesignDecision).filter(
                        DesignDecision.game_project_id == run.game_project_id,
                        DesignDecision.document_id.in_(
                            [UUID(document_id) for document_id in state["document_ids"]]
                        ),
                        DesignDecision.status == "resolved",
                        DesignDecision.decision.isnot(None),
                    ).order_by(DesignDecision.updated_at.asc()).all()
                    if decision.decision and decision.decision.strip()
                ]
                snapshot = DesignAgentEvidenceSnapshot(
                    run_id=run.id,
                    game_project_id=run.game_project_id,
                    revision=1,
                    query=plan.retrieval_query,
                    items=evidence,
                )
                run.retrieval_revision = 1
                run.model_config = {
                    **(run.model_config or {}),
                    "resolved_decisions": resolved_decisions,
                }
                db.add(snapshot)
                db.commit()
                db.refresh(snapshot)
                self._complete_execution(
                    db,
                    execution,
                    started,
                    details={
                        "evidence_snapshot_id": str(snapshot.id),
                        "evidence_count": len(evidence),
                        "section_evidence_counts": {
                            section_name: sum(
                                section_name in (item.get("matched_sections") or [])
                                for item in evidence
                            )
                            for section_name in plan.required_sections
                        },
                        "resolved_decision_count": len(resolved_decisions),
                        "resolved_decision_ids": [
                            item["decision_id"] for item in resolved_decisions
                        ],
                        "reused": False,
                    },
                )
                return {
                    "evidence_snapshot_id": str(snapshot.id),
                    "evidence_items": evidence,
                    "resolved_decisions": resolved_decisions,
                }
            except Exception as error:
                db.rollback()
                execution = db.get(DesignAgentNodeExecution, execution.id)
                run = db.get(DesignAgentRun, run.id)
                self._fail_execution(db, run, execution, started, error)
                raise

    def _generate_blueprint(self, state: DesignAgentState) -> dict[str, Any]:
        def persist(db: Session, run: DesignAgentRun, result: ProviderResult) -> dict[str, Any]:
            existing = db.query(DesignAgentArtifact).filter(
                DesignAgentArtifact.run_id == run.id,
                DesignAgentArtifact.version == 1,
            ).first()
            if existing:
                return {
                    "current_artifact_id": str(existing.id),
                    "current_artifact_version": existing.version,
                    "current_artifact": existing.content,
                }

            content = validate_generated_blueprint(
                result.content,
                state["evidence_items"],
                dialogue_policy=(run.model_config or {}).get("dialogue_policy"),
                fresh_dialogue=bool((run.model_config or {}).get("fresh_dialogue")),
                design_contract_version=(run.model_config or {}).get("design_contract_version", 1),
            )
            content = ground_blueprint_citations(content, state["evidence_items"])
            artifact = DesignAgentArtifact(
                run_id=run.id,
                game_project_id=run.game_project_id,
                evidence_snapshot_id=UUID(state["evidence_snapshot_id"]),
                version=1,
                artifact_type="draft",
                content=content,
            )
            db.add(artifact)
            db.commit()
            db.refresh(artifact)
            return {
                "current_artifact_id": str(artifact.id),
                "current_artifact_version": artifact.version,
                "current_artifact": artifact.content,
            }

        return self._provider_node(
            state,
            "generate_blueprint",
            lambda: self.provider.generate(
                {
                    **state["plan"],
                    "resolved_decisions": state.get("resolved_decisions", []),
                    "fresh_dialogue": state.get("fresh_dialogue", False),
                    "dialogue_policy": state.get("dialogue_policy"),
                    **({"defer_runtime": True} if state.get("defer_runtime") is True else {}),
                    **({"allow_unspecified_memory": True} if state.get("allow_unspecified_memory") is True else {}),
                    **({"design_contract_version": 2} if state.get("design_contract_version") == 2 else {}),
                },
                state["evidence_items"],
            ),
            persist,
        )

    def _critique(self, state: DesignAgentState) -> dict[str, Any]:
        def persist(db: Session, run: DesignAgentRun, result: ProviderResult) -> dict[str, Any]:
            artifact_id = UUID(state["current_artifact_id"])
            existing = db.query(DesignAgentCritique).filter(
                DesignAgentCritique.run_id == run.id,
                DesignAgentCritique.artifact_id == artifact_id,
                DesignAgentCritique.game_project_id == run.game_project_id,
            ).order_by(DesignAgentCritique.created_at.desc(), DesignAgentCritique.id.desc()).first()
            if existing:
                return {"critique_id": str(existing.id), "critique": existing.content}

            provenance = result.metadata.get("finding_review_provenance") or {}
            raw_review = provenance["model_output"] if provenance.get("clean") is True else result.content
            critique_content = complete_design_critique(
                raw_review, state["current_artifact"],
                review_request=saved_review_request(run), evidence=state["evidence_items"],
            )
            if result.provider_name in {"nvidia", "gemini"} and result.metadata.get("finding_review_provenance"):
                critique_content["model_review_provenance"] = copy.deepcopy(result.metadata["finding_review_provenance"])
            critique = DesignAgentCritique(
                run_id=run.id,
                artifact_id=artifact_id,
                game_project_id=run.game_project_id,
                content=critique_content,
                provider_name=result.provider_name or self.provider.name,
                model_name=result.model_name,
            )
            db.add(critique)
            db.commit()
            db.refresh(critique)
            return {"critique_id": str(critique.id), "critique": critique.content}

        return self._provider_node(
            state,
            "critique",
            lambda: self.provider.critique(
                state["current_artifact"],
                state["evidence_items"],
                review_request=canonical_review_request(state),
            ),
            persist,
        )

    def _human_review(self, state: DesignAgentState) -> dict[str, Any]:
        with self._session() as db:
            run = self._load_run(db, state)
            prior_wait = db.query(DesignAgentNodeExecution).filter(
                DesignAgentNodeExecution.run_id == run.id,
                DesignAgentNodeExecution.node_name == "human_review",
                DesignAgentNodeExecution.status == "waiting",
            ).order_by(DesignAgentNodeExecution.attempt.desc()).first()
            if prior_wait:
                prior_wait.status = "interrupted"
                prior_wait.completed_at = datetime.now(timezone.utc)
                prior_wait.details = {
                    **(prior_wait.details or {}),
                    "resumed": True,
                }
                db.commit()
            execution = self._begin_execution(
                db,
                run,
                "human_review",
                status="waiting",
                details={
                    "artifact_id": state["current_artifact_id"],
                    "artifact_version": state["current_artifact_version"],
                },
            )
            run.status = "awaiting_review"
            db.commit()
            execution_id = execution.id

        decision_payload = interrupt(
            {
                "run_id": state["run_id"],
                "artifact_id": state["current_artifact_id"],
                "artifact_version": state["current_artifact_version"],
                "critique": state["critique"],
                "allowed_actions": ["approve", "reject"],
            }
        )

        started = time.perf_counter()
        decision = ResumeDecision.model_validate(decision_payload)
        with self._session() as db:
            run = self._load_run(db, state)
            decision.require_current_artifact(state["current_artifact_id"])
            if decision.decision == "approve":
                require_degraded_acknowledgement(db, run, decision.acknowledge_degraded)
            if decision.decision == "approve" and requires_design_quality_review(run, decision.confirmed_proposals):
                latest = db.query(DesignAgentArtifact).filter(
                    DesignAgentArtifact.run_id == run.id,
                    DesignAgentArtifact.game_project_id == run.game_project_id,
                    DesignAgentArtifact.artifact_type != "final",
                ).order_by(DesignAgentArtifact.version.desc()).first()
                if (latest is None or str(latest.id) != state["current_artifact_id"]
                        or latest.content != state["current_artifact"]):
                    raise ValueError("Review the current draft; the queued approval is stale.")
                validate_persisted_design_approval(
                    db, run, latest,
                    [item.model_dump() for item in decision.confirmed_proposals],
                    expected={"content": state["current_artifact"], "evidence": state["evidence_items"],
                              "critique": state["critique"]},
                    acknowledge_degraded=decision.acknowledge_degraded,
                )
            existing = db.query(DesignAgentReviewEvent).filter(
                DesignAgentReviewEvent.artifact_id == UUID(state["current_artifact_id"])
            ).first()
            if existing and existing.decision != decision.decision:
                raise RuntimeError("This artifact already has a different review decision.")
            if existing and decision.acknowledge_degraded:
                existing.details = {**(existing.details or {}), "acknowledge_degraded": True}
            if existing is None:
                db.add(
                    DesignAgentReviewEvent(
                        run_id=run.id,
                        artifact_id=UUID(state["current_artifact_id"]),
                        reviewer_user_id=UUID(decision.reviewer_user_id) if decision.reviewer_user_id else None,
                        reviewer_label=decision.reviewer_label,
                        decision=decision.decision,
                        reason=decision.reason,
                        details={"acknowledge_degraded": decision.acknowledge_degraded},
                        game_project_id=run.game_project_id,
                    )
            )
            run.status = "approved" if decision.decision == "approve" else "revision_requested"
            db.commit()
            execution = db.get(DesignAgentNodeExecution, execution_id)
            self._complete_execution(
                db,
                execution,
                started,
                details={
                    "artifact_id": state["current_artifact_id"],
                    "decision": decision.decision,
                    "artifact_version": state["current_artifact_version"],
                    "target_sections": decision.target_sections,
                    "confirmed_proposals": [item.model_dump() for item in decision.confirmed_proposals],
                    "acknowledge_degraded": decision.acknowledge_degraded,
                    "reviewer_label": decision.reviewer_label,
                    "reviewer_user_id": decision.reviewer_user_id,
                },
            )
        return {
            "review_decision": decision.decision,
            "finalization_failed": False,
            "rejection_reason": decision.reason or "",
            "revision_targets": review_targets(decision.reason or "", decision.target_sections) if decision.decision == "reject" else [],
            "confirmed_proposals": [item.model_dump() for item in decision.confirmed_proposals],
            "acknowledge_degraded": decision.acknowledge_degraded,
        }

    @staticmethod
    def _route_after_review(state: DesignAgentState) -> str:
        if state["review_decision"] == "approve":
            return "approve"
        if state.get("revision_count", 0) >= state["max_revisions"]:
            return "revision_limit"
        return "reject"

    def _revise(self, state: DesignAgentState) -> dict[str, Any]:
        def persist(db: Session, run: DesignAgentRun, result: ProviderResult) -> dict[str, Any]:
            next_version = state["current_artifact_version"] + 1
            existing = db.query(DesignAgentArtifact).filter(
                DesignAgentArtifact.run_id == run.id,
                DesignAgentArtifact.version == next_version,
            ).first()
            if existing:
                run.revision_count = max(run.revision_count, next_version - 1)
                run.model_config = {**(run.model_config or {}), "consecutive_revision_failures": 0}
                db.commit()
                return {
                    "current_artifact_id": str(existing.id),
                    "current_artifact_version": existing.version,
                    "current_artifact": existing.content,
                    "revision_count": run.revision_count,
                    "revision_failed": False,
                }

            content = validate_generated_blueprint(
                result.content,
                state["evidence_items"],
                dialogue_policy=(run.model_config or {}).get("dialogue_policy"),
                fresh_dialogue=bool((run.model_config or {}).get("fresh_dialogue")),
                design_contract_version=(run.model_config or {}).get("design_contract_version", 1),
            )
            content = ground_blueprint_citations(content, state["evidence_items"])
            targets = state.get("revision_targets") or review_targets(state["rejection_reason"])
            # Normalization must not rewrite a historical unrelated section.
            for section in state["current_artifact"]:
                if section not in targets:
                    content[section] = copy.deepcopy(state["current_artifact"][section])
            validate_structured_revision(
                state["current_artifact"],
                content,
                state["rejection_reason"],
                target_sections=targets,
                evidence=state["evidence_items"],
            )
            artifact = DesignAgentArtifact(
                run_id=run.id,
                game_project_id=run.game_project_id,
                evidence_snapshot_id=UUID(state["evidence_snapshot_id"]),
                version=next_version,
                artifact_type="revision",
                content=content,
            )
            run.revision_count += 1
            run.model_config = {**(run.model_config or {}), "consecutive_revision_failures": 0}
            db.add(artifact)
            db.commit()
            db.refresh(artifact)
            return {
                "current_artifact_id": str(artifact.id),
                "current_artifact_version": artifact.version,
                "current_artifact": artifact.content,
                "revision_count": run.revision_count,
                "revision_failed": False,
            }

        return self._provider_node(
            state,
            "revise",
            lambda: self.provider.revise(
                state["current_artifact"],
                state["evidence_items"],
                state["rejection_reason"],
                target_sections=state.get("revision_targets") or review_targets(state["rejection_reason"]),
                review_request=canonical_review_request(state),
            ),
            persist,
        )

    def _revision_limit(self, state: DesignAgentState) -> dict[str, Any]:
        with self._session() as db:
            run = self._load_run(db, state)
            execution = self._begin_execution(db, run, "revision_limit")
            started = time.perf_counter()
            run.status = "revision_limit_reached"
            run.last_error = "Maximum human-requested revision count reached."
            db.commit()
            self._complete_execution(db, execution, started)
        return {}

    def _finalize(self, state: DesignAgentState) -> dict[str, Any]:
        with self._session() as db:
            run = self._load_run(db, state)
            execution = self._begin_execution(db, run, "finalize")
            started = time.perf_counter()
            try:
                existing = db.query(DesignAgentArtifact).filter(
                    DesignAgentArtifact.run_id == run.id,
                    DesignAgentArtifact.artifact_type == "final",
                ).first()
                if existing:
                    self._complete_execution(db, execution, started, details={"reused": True})
                    return {
                        "final_artifact_id": str(existing.id),
                        "blueprint_id": str(existing.blueprint_id),
                    }

                latest = db.query(DesignAgentArtifact).filter(
                    DesignAgentArtifact.run_id == run.id,
                    DesignAgentArtifact.game_project_id == run.game_project_id,
                    DesignAgentArtifact.artifact_type != "final",
                ).order_by(DesignAgentArtifact.version.desc()).first()
                if latest is None or str(latest.id) != state["current_artifact_id"]:
                    raise ValueError("Review the current draft; the approval is stale.")
                integrity_error = (
                    "Finalization blocked: candidate content differs from the reviewed artifact outside "
                    "the documented server-metadata exceptions. No blueprint or final artifact was saved; "
                    "the reviewed draft is unchanged."
                )
                if content_digest(state["current_artifact"]) != content_digest(latest.content):
                    raise FinalizationIntegrityError(integrity_error)
                if requires_design_quality_review(run, state.get("confirmed_proposals")):
                    validate_persisted_design_approval(
                        db, run, latest, state.get("confirmed_proposals"),
                        expected={"content": state["current_artifact"], "evidence": state["evidence_items"],
                                  "critique": state["critique"]}, acknowledge_degraded=state.get("acknowledge_degraded", False))
                require_degraded_acknowledgement(db, run, state.get("acknowledge_degraded", False))
                content = validate_generated_blueprint(
                    state["current_artifact"],
                    state["evidence_items"],
                    require_actionable=self.provider.name in {"nvidia", "gemini"},
                    design_contract_version=(run.model_config or {}).get("design_contract_version", 1),
                )
                expected_content = copy.deepcopy(latest.content)
                # Only these server-owned metadata additions may differ from reviewed content.
                # They remain final-only because section validation discards these extra fields.
                if (run.model_config or {}).get("defer_runtime") is True:
                    for snapshot_content in (content, expected_content):
                        snapshot_content["unity_runtime_preview"]["runtime_deferred"] = True
                        snapshot_content["unity_runtime_preview"]["warnings"] = list(dict.fromkeys([
                            *snapshot_content["unity_runtime_preview"]["warnings"],
                            "Runtime integration explicitly deferred. Approved design only; no runtime release or materialization.",
                        ]))
                if memory_is_unspecified(latest.content, saved_review_request(run)):
                    content["npc_memory_design"]["memory_unspecified"] = True
                    expected_content["npc_memory_design"]["memory_unspecified"] = True
                first_document = db.query(Document).filter(
                    Document.id == UUID(run.document_ids[0]),
                    Document.game_project_id == run.game_project_id,
                ).first()
                title = first_document.title if first_document else "Game design"
                if content_digest(content) != content_digest(expected_content):
                    raise FinalizationIntegrityError(integrity_error)
                blueprint = GameBlueprint(
                    title=f"Agent Blueprint: {title}",
                    document_id=UUID(run.document_ids[0]),
                    source_document_ids=run.document_ids,
                    game_project_id=run.game_project_id,
                    summary=content["summary"],
                    narrative_direction=content["narrative_direction"],
                    art_style_direction=content["art_style_direction"],
                    npc_archetypes=content["npc_archetypes"],
                    npc_memory_design=content["npc_memory_design"],
                    level_design_suggestions=content["level_design_suggestions"],
                    gameplay_systems=content["gameplay_systems"],
                    quest_hooks=content["quest_hooks"],
                    unity_runtime_preview=content["unity_runtime_preview"],
                    status="approved",
                )
                db.add(blueprint)
                db.flush()

                final_artifact = DesignAgentArtifact(
                    run_id=run.id,
                    game_project_id=run.game_project_id,
                    evidence_snapshot_id=UUID(state["evidence_snapshot_id"]),
                    blueprint_id=blueprint.id,
                    version=state["current_artifact_version"] + 1,
                    artifact_type="final",
                    content=content,
                    immutable=True,
                )
                run.status = "completed"
                run.current_node = "finalize"
                run.completed_at = datetime.now(timezone.utc)
                run.last_error = None
                db.add(final_artifact)
                db.commit()
                db.refresh(final_artifact)
                self._complete_execution(
                    db,
                    execution,
                    started,
                    details={
                        "final_artifact_id": str(final_artifact.id),
                        "blueprint_id": str(blueprint.id),
                        "reused": False,
                    },
                )
                return {
                    "final_artifact_id": str(final_artifact.id),
                    "blueprint_id": str(blueprint.id),
                }
            except Exception as error:
                db.rollback()
                execution = db.get(DesignAgentNodeExecution, execution.id)
                run = db.get(DesignAgentRun, run.id)
                self._fail_execution(db, run, execution, started, error)
                if isinstance(error, FinalizationIntegrityError):
                    run.status = "awaiting_review"
                    run.current_node = "human_review"
                    db.commit()
                    return {"finalization_failed": True}
                raise
