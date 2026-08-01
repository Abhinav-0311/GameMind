import time
from contextlib import contextmanager
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
    BlueprintContent,
    CritiqueOutput,
    DesignAgentState,
    ResearchPlan,
    ResumeDecision,
)
from app.design_agent.grounding import (
    ground_blueprint_citations,
    validate_structured_revision,
)
from app.design_agent.provider import (
    DesignAgentProvider,
    MockDesignAgentProvider,
    ProviderResult,
)
from app.models.blueprint import GameBlueprint
from app.models.design_agent import (
    DesignAgentArtifact,
    DesignAgentCritique,
    DesignAgentEvidenceSnapshot,
    DesignAgentNodeExecution,
    DesignAgentReviewEvent,
    DesignAgentRun,
)
from app.models.document import Document
from app.services.rag_service import RAGService


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
        graph.add_edge("revise", "critique")
        graph.add_edge("revision_limit", END)
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=saver)

    def start(self, run: DesignAgentRun) -> dict[str, Any]:
        initial_state: DesignAgentState = {
            "run_id": str(run.id),
            "game_project_id": run.game_project_id,
            "objective": run.objective,
            "document_ids": [str(document_id) for document_id in run.document_ids],
            "max_revisions": run.max_revisions,
            "revision_count": run.revision_count,
        }
        with self._checkpointer() as saver:
            return self._compile(saver).invoke(initial_state, self._thread_config(run.id))

    def resume(self, run_id: UUID, decision: ResumeDecision) -> dict[str, Any]:
        with self._checkpointer() as saver:
            return self._compile(saver).invoke(
                Command(resume=decision.model_dump()),
                self._thread_config(run_id),
            )

    @contextmanager
    def _session(self) -> Iterator[Session]:
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()

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
    ) -> None:
        execution.status = "failed"
        execution.error = str(error)
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
            execution = self._begin_execution(
                db,
                run,
                node_name,
                provider_name=self.provider.name,
            )
            started = time.perf_counter()
            try:
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
                        **result.metadata,
                    },
                )
                return update
            except Exception as error:
                db.rollback()
                execution = db.get(DesignAgentNodeExecution, execution.id)
                run = db.get(DesignAgentRun, run.id)
                self._fail_execution(db, run, execution, started, error)
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
                    self._complete_execution(
                        db,
                        execution,
                        started,
                        details={"evidence_snapshot_id": str(existing.id), "reused": True},
                    )
                    return {
                        "evidence_snapshot_id": str(existing.id),
                        "evidence_items": existing.items,
                    }

                plan = ResearchPlan.model_validate(state["plan"])
                evidence = self.rag_service.query_lore_sections(
                    plan.section_queries,
                    limit_per_section=3,
                    game_project_id=run.game_project_id,
                    document_ids=state["document_ids"],
                )
                snapshot = DesignAgentEvidenceSnapshot(
                    run_id=run.id,
                    game_project_id=run.game_project_id,
                    revision=1,
                    query=plan.retrieval_query,
                    items=evidence,
                )
                run.retrieval_revision = 1
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
                        "reused": False,
                    },
                )
                return {
                    "evidence_snapshot_id": str(snapshot.id),
                    "evidence_items": evidence,
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

            content = ground_blueprint_citations(
                result.content,
                state["evidence_items"],
            )
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
            lambda: self.provider.generate(state["plan"], state["evidence_items"]),
            persist,
        )

    def _critique(self, state: DesignAgentState) -> dict[str, Any]:
        def persist(db: Session, run: DesignAgentRun, result: ProviderResult) -> dict[str, Any]:
            artifact_id = UUID(state["current_artifact_id"])
            existing = db.query(DesignAgentCritique).filter(
                DesignAgentCritique.run_id == run.id,
                DesignAgentCritique.artifact_id == artifact_id,
            ).first()
            if existing:
                return {"critique_id": str(existing.id), "critique": existing.content}

            critique_content = CritiqueOutput.model_validate(result.content).model_dump()
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
            existing = db.query(DesignAgentReviewEvent).filter(
                DesignAgentReviewEvent.artifact_id == UUID(state["current_artifact_id"])
            ).first()
            if existing and existing.decision != decision.decision:
                raise RuntimeError("This artifact already has a different review decision.")
            if existing is None:
                db.add(
                    DesignAgentReviewEvent(
                        run_id=run.id,
                        artifact_id=UUID(state["current_artifact_id"]),
                        reviewer_user_id=UUID(decision.reviewer_user_id) if decision.reviewer_user_id else None,
                        reviewer_label=decision.reviewer_label,
                        decision=decision.decision,
                        reason=decision.reason,
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
                },
            )
        return {
            "review_decision": decision.decision,
            "rejection_reason": decision.reason or "",
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
                db.commit()
                return {
                    "current_artifact_id": str(existing.id),
                    "current_artifact_version": existing.version,
                    "current_artifact": existing.content,
                    "revision_count": run.revision_count,
                }

            content = ground_blueprint_citations(
                result.content,
                state["evidence_items"],
            )
            validate_structured_revision(
                state["current_artifact"],
                content,
                state["rejection_reason"],
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
            db.add(artifact)
            db.commit()
            db.refresh(artifact)
            return {
                "current_artifact_id": str(artifact.id),
                "current_artifact_version": artifact.version,
                "current_artifact": artifact.content,
                "revision_count": run.revision_count,
            }

        return self._provider_node(
            state,
            "revise",
            lambda: self.provider.revise(
                state["current_artifact"],
                state["evidence_items"],
                state["rejection_reason"],
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

                content = BlueprintContent.model_validate(state["current_artifact"]).model_dump()
                first_document = db.query(Document).filter(
                    Document.id == UUID(run.document_ids[0]),
                    Document.game_project_id == run.game_project_id,
                ).first()
                title = first_document.title if first_document else "Game design"
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
                raise
