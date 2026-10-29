from uuid import UUID
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.design_agent.contracts import ResumeDecision
from app.design_agent.jobs import DesignAgentJobService
from app.design_agent.provider_factory import build_design_agent_provider
from app.design_agent.llm_provider import NvidiaProviderError
from app.design_agent.grounding import OFFLINE_REVISION_UNAVAILABLE
from app.design_agent.schemas import (
    DesignAgentArtifactResponse,
    DesignAgentCritiqueResponse,
    DesignAgentEvidenceResponse,
    DesignAgentCritiqueRetryRequest,
    DesignAgentRunCreate,
    DesignAgentRunResponse,
    DesignAgentRuntimeExportResponse,
    DesignAgentTraceItem,
    DesignAgentTraceResponse,
)
from app.design_agent.workflow import DesignAgentWorkflow
from app.design_agent.review_policy import requires_design_quality_review, validate_persisted_design_approval, degraded_review_required, require_degraded_acknowledgement
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
from app.models.user import User
from app.services.blueprint_brief_service import BlueprintBriefService


REJECTED_DRAFT_APPROVAL_MESSAGE = (
    "This draft already has a recorded rejection. The correction failed and no "
    "revised draft was saved, so this draft cannot currently be approved. Request "
    "another correction or start a new isolated run."
)


class DesignAgentService:
    _ACTIVE_RUN_STATUSES = ("created", "queued", "running", "review_queued", "awaiting_review")

    def __init__(self, workflow: DesignAgentWorkflow | None = None):
        self._workflow = workflow

    @property
    def workflow(self) -> DesignAgentWorkflow:
        # Read-only run, trace, and export endpoints should not require Chroma.
        if self._workflow is None:
            self._workflow = DesignAgentWorkflow(
                database_url=settings.DATABASE_URL,
                session_factory=SessionLocal,
                provider=build_design_agent_provider(),
            )
        return self._workflow

    @staticmethod
    def _get_run(db: Session, run_id: UUID, game_project_id: str) -> DesignAgentRun:
        run = db.query(DesignAgentRun).filter(
            DesignAgentRun.id == run_id,
            DesignAgentRun.game_project_id == game_project_id,
        ).first()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Design-agent run not found in the active workspace.",
            )
        return run

    @staticmethod
    def _response(db: Session, run: DesignAgentRun) -> DesignAgentRunResponse:
        artifact = db.query(DesignAgentArtifact).filter(
            DesignAgentArtifact.run_id == run.id,
            DesignAgentArtifact.game_project_id == run.game_project_id,
        ).order_by(DesignAgentArtifact.version.desc()).first()
        reviewed_artifact = artifact
        if artifact and artifact.artifact_type == "final":
            # Final snapshots retain the review of the draft that was approved.
            reviewed_artifact = db.query(DesignAgentArtifact).filter(
                DesignAgentArtifact.run_id == run.id,
                DesignAgentArtifact.game_project_id == run.game_project_id,
                DesignAgentArtifact.artifact_type != "final",
                DesignAgentArtifact.version < artifact.version,
            ).order_by(DesignAgentArtifact.version.desc()).first()
        critique = db.query(DesignAgentCritique).filter(
            DesignAgentCritique.run_id == run.id,
            DesignAgentCritique.game_project_id == run.game_project_id,
            DesignAgentCritique.artifact_id == reviewed_artifact.id,
        ).order_by(DesignAgentCritique.created_at.desc(), DesignAgentCritique.id.desc()).first() if reviewed_artifact else None
        rejected = db.query(DesignAgentReviewEvent.id).filter(
            DesignAgentReviewEvent.run_id == run.id,
            DesignAgentReviewEvent.game_project_id == run.game_project_id,
            DesignAgentReviewEvent.artifact_id == artifact.id,
            DesignAgentReviewEvent.decision == "reject").first() if artifact and artifact.artifact_type != "final" else None
        return DesignAgentRunResponse(
            id=run.id,
            game_project_id=run.game_project_id,
            objective=run.objective,
            document_ids=[str(document_id) for document_id in run.document_ids],
            status=run.status,
            current_node=run.current_node,
            provider_name=run.provider_name,
            degraded=degraded_review_required(db, run),
            defer_runtime=(run.model_config or {}).get("defer_runtime") is True,
            allow_unspecified_memory=(run.model_config or {}).get("allow_unspecified_memory") is True,
            retrieval_revision=run.retrieval_revision,
            revision_count=run.revision_count,
            max_revisions=run.max_revisions,
            consecutive_revision_failures=(run.model_config or {}).get("consecutive_revision_failures", 0),
            max_consecutive_revision_failures=settings.DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES,
            last_error=run.last_error,
            approval_blocked_reason=REJECTED_DRAFT_APPROVAL_MESSAGE if rejected else None,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
            current_artifact=DesignAgentArtifactResponse.model_validate(artifact) if artifact else None,
            critique=DesignAgentCritiqueResponse.model_validate(critique) if critique else None,
        )

    def create_and_start(
        self,
        db: Session,
        payload: DesignAgentRunCreate,
        game_project_id: str,
        current_user: User | None,
    ) -> DesignAgentRunResponse:
        document_ids = list(dict.fromkeys(payload.document_ids))
        document_id_values = [str(document_id) for document_id in document_ids]
        documents = db.query(Document).filter(
            Document.id.in_(document_ids),
            Document.game_project_id == game_project_id,
        ).all()
        if len(documents) != len(document_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more source documents were not found in the active workspace.",
            )
        if any(not document.chunks for document in documents):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Every selected source must be indexed before the design-agent run starts.",
            )

        existing_run = db.query(DesignAgentRun).filter(
            DesignAgentRun.game_project_id == game_project_id,
            DesignAgentRun.status.in_(self._ACTIVE_RUN_STATUSES),
            or_(
                DesignAgentRun.status != "awaiting_review",
                and_(DesignAgentRun.revision_count < DesignAgentRun.max_revisions,
                     func.coalesce(DesignAgentRun.model_config["consecutive_revision_failures"].as_integer(), 0)
                     < settings.DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES),
            ),
            DesignAgentRun.document_ids.contains(document_id_values),
        ).first()
        if existing_run:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A governed review is already active for this GDD ({existing_run.id}).",
            )

        provider = self.workflow.provider if self._workflow is not None else build_design_agent_provider()
        if provider.name in {"nvidia", "gemini"} and not payload.hosted_provider_consent:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Explicit consent is required before selected evidence is sent to the configured hosted provider.",
            )
        if provider.name == "gemini":
            primary = getattr(provider, "primary", provider)
            try:
                primary.llm_provider.preflight()
            except NvidiaProviderError as error:
                raise HTTPException(status_code=503 if error.code == "budget_unavailable" else 429,
                    detail={"code": error.code, "message": str(error)}) from None
        run = DesignAgentRun(
            game_project_id=game_project_id,
            created_by_user_id=current_user.id if current_user else None,
            objective=payload.objective.strip(),
            document_ids=document_id_values,
            provider_name=provider.name,
            model_config={
                "phase": "phase_8",
                **provider.configuration(),
                "hosted_provider_consent": provider.name in {"nvidia", "gemini"},
                "consented_document_ids": document_id_values if provider.name in {"nvidia", "gemini"} else [],
                "degraded": False,
                "fresh_dialogue": payload.fresh_dialogue,
                "dialogue_policy": payload.dialogue_policy,
                "defer_runtime": payload.defer_runtime,
                "allow_unspecified_memory": payload.allow_unspecified_memory,
            },
            max_revisions=payload.max_revisions,
        )
        db.add(run)
        if settings.DESIGN_AGENT_EXECUTION_MODE == "queued":
            db.flush()
            DesignAgentJobService.enqueue_start(db, run)
            db.commit()
            db.refresh(run)
            return self._response(db, run)
        db.commit()
        db.refresh(run)

        try:
            self.workflow.start(run)
        except Exception as error:
            db.expire_all()
            failed_run = self._get_run(db, run.id, game_project_id)
            if failed_run.status != "failed":
                failed_run.status = "failed"
                failed_run.last_error = str(error)
                db.commit()
            raise HTTPException(
                status_code=self._failure_status(db, failed_run, 503),
                detail={
                    "message": "The design-agent workflow could not start. Inspect the saved run trace for details.",
                    "run_id": str(failed_run.id),
                },
            ) from error
        db.expire_all()
        run = self._get_run(db, run.id, game_project_id)
        return self._response(db, run)

    def list_runs(self, db: Session, game_project_id: str) -> list[DesignAgentRunResponse]:
        runs = db.query(DesignAgentRun).filter(
            DesignAgentRun.game_project_id == game_project_id
        ).order_by(DesignAgentRun.created_at.desc()).all()
        return [self._response(db, run) for run in runs]

    def get_run(self, db: Session, run_id: UUID, game_project_id: str) -> DesignAgentRunResponse:
        return self._response(db, self._get_run(db, run_id, game_project_id))

    def get_artifact_evidence(
        self, db: Session, run_id: UUID, artifact_id: UUID, game_project_id: str,
    ) -> DesignAgentEvidenceResponse:
        """Read the artifact's frozen snapshot, never current document chunks."""
        self._get_run(db, run_id, game_project_id)
        artifact = db.query(DesignAgentArtifact).filter(
            DesignAgentArtifact.id == artifact_id,
            DesignAgentArtifact.run_id == run_id,
            DesignAgentArtifact.game_project_id == game_project_id,
        ).first()
        if artifact is None:
            raise HTTPException(status_code=404, detail="Review artifact not found in this workspace and run.")
        snapshot = db.query(DesignAgentEvidenceSnapshot).filter(
            DesignAgentEvidenceSnapshot.id == artifact.evidence_snapshot_id,
            DesignAgentEvidenceSnapshot.run_id == run_id,
            DesignAgentEvidenceSnapshot.game_project_id == game_project_id,
        ).first()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="The artifact's frozen evidence snapshot is unavailable.")
        return DesignAgentEvidenceResponse(
            artifact_id=artifact.id, snapshot_id=snapshot.id,
            revision=snapshot.revision, items=snapshot.items or [],
        )

    def retry_critique(
        self, db: Session, run_id: UUID, game_project_id: str, payload: DesignAgentCritiqueRetryRequest,
        current_user: User | None = None,
    ) -> DesignAgentRunResponse:
        run = db.query(DesignAgentRun).filter_by(id=run_id, game_project_id=game_project_id).with_for_update().first()
        if run is None:
            raise HTTPException(status_code=404, detail="Design-agent run not found in the active workspace.")
        artifact = db.query(DesignAgentArtifact).filter_by(run_id=run_id, game_project_id=game_project_id).order_by(
            DesignAgentArtifact.version.desc()).first()
        failed = db.query(DesignAgentNodeExecution).filter_by(run_id=run_id, game_project_id=game_project_id,
            node_name="critique").order_by(DesignAgentNodeExecution.attempt.desc()).first()
        if (run.status != "failed" or run.current_node != "critique" or not artifact or artifact.immutable
                or artifact.id != payload.artifact_id or not failed or failed.status != "failed"
                or failed.id != payload.failed_execution_id
                or db.query(DesignAgentCritique).filter_by(run_id=run_id, artifact_id=artifact.id).first()
                or db.query(DesignAgentJob).filter(DesignAgentJob.run_id == run_id,
                    DesignAgentJob.status.in_(("pending", "running"))).first()):
            raise HTTPException(status_code=409, detail="Refresh the run; only its exact failed critique and current unreviewed draft can be retried.")
        if self.workflow.provider.name != run.provider_name:
            raise HTTPException(status_code=409, detail="The configured provider changed. Start a new run with fresh provider consent.")
        if run.provider_name in {"nvidia", "gemini"} and (not payload.hosted_provider_consent
                or not (run.model_config or {}).get("hosted_provider_consent")
                or set((run.model_config or {}).get("consented_document_ids", [])) != set(run.document_ids)):
            raise HTTPException(status_code=409, detail="Explicit consent for the saved draft and selected source excerpts is required.")
        key = f"critique:{run.id}:{failed.id}"
        if db.query(DesignAgentJob).filter_by(idempotency_key=key).first():
            raise HTTPException(status_code=409, detail="This failed critique already has a retry request. Refresh the run.")
        job = DesignAgentJob(run_id=run.id, game_project_id=game_project_id, operation="retry_critique",
            payload={"artifact_id": str(artifact.id), "failed_execution_id": str(failed.id),
                     "hosted_provider_consent": payload.hosted_provider_consent,
                     "reviewer_user_id": str(current_user.id) if current_user else None},
            idempotency_key=key, max_attempts=1)
        run.status = "review_queued"
        if settings.DESIGN_AGENT_EXECUTION_MODE != "queued":
            # Reserve only this inline request before workers can claim it.
            job.status, job.locked_by, job.attempts = "running", "inline-critique-retry", 1
            job.locked_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        if settings.DESIGN_AGENT_EXECUTION_MODE == "queued":
            return self._response(db, run)
        worker = DesignAgentJobService(self.workflow.session_factory, workflow_factory=lambda _: self.workflow)
        worker.execute(job.id)
        db.expire_all()
        run = self._get_run(db, run_id, game_project_id)
        if run.status == "failed":
            raise HTTPException(status_code=self._failure_status(db, run, 503), detail={"message": "Critique retry failed; the saved draft and evidence are unchanged. Inspect the trace.", "run_id": str(run.id)})
        return self._response(db, run)

    def review(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
        decision: str,
        reason: str | None,
        current_user: User | None,
        target_sections: list[str] | None = None,
        artifact_id: UUID | None = None,
        confirmed_proposals: list[dict] | None = None,
        acknowledge_degraded: bool = False,
        target_paths: list[str] | None = None,
    ) -> DesignAgentRunResponse:
        run = self._get_run(db, run_id, game_project_id)
        if run.status != "awaiting_review":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This run cannot be reviewed while its status is '{run.status}'.",
            )
        if decision != 'request_correction' and db.query(DesignAgentNodeExecution.id).filter(
                DesignAgentNodeExecution.run_id == run.id,
                DesignAgentNodeExecution.node_name == 'correction_request',
                DesignAgentNodeExecution.status.in_(['pending', 'running'])).first():
            raise HTTPException(status_code=409, detail='A correction is active. Wait for its outcome before reviewing this draft.')
        if decision in {"reject", "request_correction"} and run.revision_count >= run.max_revisions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This run's revision budget is exhausted. Start a new run with "
                    "a clearer objective and fresh provider consent. The current draft is unchanged."
                ),
            )
        if (decision in {"reject", "request_correction"} and (run.model_config or {}).get("consecutive_revision_failures", 0)
                >= settings.DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES):
            raise HTTPException(status_code=409, detail="Consecutive failed revision limit reached. No further revision request was sent; start a new run with fresh consent. The draft is unchanged.")
        if decision == "approve":
            try:
                require_degraded_acknowledgement(db, run, acknowledge_degraded)
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
        requires_quality_review = requires_design_quality_review(run, confirmed_proposals)
        artifact = db.query(DesignAgentArtifact).filter(
            DesignAgentArtifact.run_id == run.id,
            DesignAgentArtifact.game_project_id == game_project_id,
        ).order_by(DesignAgentArtifact.version.desc()).first()
        if artifact_id is not None or (decision == "approve" and requires_quality_review):
            if artifact is None or (artifact_id is not None and artifact.id != artifact_id):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="Review the current draft; the selected artifact is unavailable or stale.")
        existing_review = db.query(DesignAgentReviewEvent).filter(
            DesignAgentReviewEvent.run_id == run.id,
            DesignAgentReviewEvent.game_project_id == game_project_id,
            DesignAgentReviewEvent.artifact_id == artifact.id).first() if artifact else None
        if existing_review and existing_review.decision != decision and decision != 'request_correction':
            raise HTTPException(status_code=409, detail=(REJECTED_DRAFT_APPROVAL_MESSAGE
                if existing_review.decision == "reject" else
                "This draft already has a recorded approval and cannot currently be rejected."))
        if (confirmed_proposals or acknowledge_degraded) and artifact_id is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Proposal confirmation or degraded acknowledgement requires the exact artifact_id.")
        if decision == "approve" and requires_quality_review:
            try:
                validate_persisted_design_approval(db, run, artifact, confirmed_proposals, acknowledge_degraded=acknowledge_degraded)
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This draft needs revision before approval: " + str(error)
                    ),
                ) from error
        if decision == 'request_correction':
            from app.design_agent.field_corrections import validate_target_paths
            if artifact is None or artifact.immutable or artifact_id != artifact.id:
                raise HTTPException(status_code=409, detail='A correction requires the current mutable artifact_id.')
            try:
                target_paths = validate_target_paths(target_paths, artifact.content)
                ResumeDecision(decision=decision, reason=reason, artifact_id=artifact_id, target_paths=target_paths)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        resume_decision = ResumeDecision(
            decision=decision,
            reason=reason.strip() if reason else None,
            reviewer_user_id=str(current_user.id) if current_user else None,
            reviewer_label=current_user.email if current_user else "local_developer",
            target_sections=target_sections,
            artifact_id=artifact.id if artifact else None,
            confirmed_proposals=confirmed_proposals or [],
            acknowledge_degraded=acknowledge_degraded,
            target_paths=target_paths,
        )
        if decision == 'request_correction':
            from app.design_agent.field_corrections import correction_effects, pointer_value
            from app.design_agent.finding_reviews import content_digest
            # Reserve under the run lock, then release it before graph/provider work.
            db.refresh(run, with_for_update=True)
            latest = db.query(DesignAgentArtifact).filter_by(run_id=run.id).order_by(DesignAgentArtifact.version.desc()).first()
            if run.status != 'awaiting_review' or latest.id != artifact.id or latest.immutable:
                db.rollback()
                raise HTTPException(status_code=409, detail='The review context changed; refresh the current mutable draft.')
            fingerprint = content_digest({'action': decision, 'artifact_id': str(artifact.id),
                                          'target_paths': target_paths, 'reason': resume_decision.reason})
            previous = db.query(DesignAgentNodeExecution).filter_by(run_id=run.id,
                game_project_id=game_project_id, node_name='correction_request').all()
            if any(item.status in {'pending', 'running'} or (item.details or {}).get('request_key') == fingerprint for item in previous):
                db.rollback()
                raise HTTPException(status_code=409, detail='This correction is already submitted or another correction is active. No new work was started.')
            reservation = DesignAgentNodeExecution(run_id=run.id, game_project_id=game_project_id,
                node_name='correction_request', attempt=max((item.attempt for item in previous), default=0) + 1,
                status='pending', details={'action': decision, 'request_key': fingerprint,
                    'artifact_id': str(artifact.id), 'artifact_version': artifact.version,
                    'artifact_sha256': content_digest(artifact.content), 'target_paths': target_paths,
                    'current_values': {path: pointer_value(artifact.content, path) for path in target_paths},
                    'dependent_effects': [correction_effects(path) for path in target_paths],
                    'reason': resume_decision.reason, 'reviewer_label': resume_decision.reviewer_label,
                    'reviewer_user_id': resume_decision.reviewer_user_id, 'outcome': 'pending'})
            db.add(reservation)
            db.flush()
            resume_decision.correction_request_id = reservation.id
            run.status = 'review_queued'
        if settings.DESIGN_AGENT_EXECUTION_MODE == "queued":
            artifact = db.query(DesignAgentArtifact).filter(
                DesignAgentArtifact.run_id == run.id,
                DesignAgentArtifact.game_project_id == game_project_id,
            ).order_by(DesignAgentArtifact.version.desc()).first()
            if artifact is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The review artifact is unavailable.",
                )
            DesignAgentJobService.enqueue_resume(db, run, resume_decision, artifact.id)
            db.commit()
            db.refresh(run)
            return self._response(db, run)
        if decision == 'request_correction':
            db.commit()
        try:
            resumed = self.workflow.resume(
                run.id,
                resume_decision,
            )
        except Exception as error:
            raise HTTPException(
                status_code=self._failure_status(db, self._get_run(db, run_id, game_project_id), 500),
                detail="The design-agent workflow could not resume. Inspect the run trace for details.",
            ) from error
        db.expire_all()
        if isinstance(resumed, dict) and resumed.get("finalization_failed"):
            run = self._get_run(db, run_id, game_project_id)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=run.last_error)
        if isinstance(resumed, dict) and resumed.get("revision_failed"):
            run = self._get_run(db, run_id, game_project_id)
            remaining = max(0, run.max_revisions - run.revision_count)
            failures = (run.model_config or {}).get("consecutive_revision_failures", 0)
            limit = settings.DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES
            message = (OFFLINE_REVISION_UNAVAILABLE + " The previous draft and critique are unchanged. "
                       if run.provider_name == "mock" and run.last_error == OFFLINE_REVISION_UNAVAILABLE
                       else "The revision failed; the previous draft and critique are unchanged. ")
            if decision == 'request_correction':
                message = 'The correction failed; the previous draft and critique are unchanged. No rejection was recorded. The draft can still be approved if its other review gates allow. '
            raise HTTPException(status_code=self._failure_status(db, run, 409, node_name="revise"),
                detail=message +
                f"No revision was consumed; {remaining} successful revision slot(s) remain. "
                f"Consecutive failed revisions: {failures}/{limit}. "
                + ("Failed revision limit reached; start a new run with fresh consent." if failures >= limit
                   else "Inspect the failed revision in the trace before trying again."))
        return self._response(db, self._get_run(db, run_id, game_project_id))

    @staticmethod
    def _failure_status(db, run, default, *, node_name=None):
        execution = db.query(DesignAgentNodeExecution).filter_by(
            run_id=run.id, node_name=node_name or run.current_node, status="failed").order_by(
            DesignAgentNodeExecution.started_at.desc(), DesignAgentNodeExecution.attempt.desc()).first()
        return (execution.details or {}).get("http_status", default) if execution else default

    def trace(self, db: Session, run_id: UUID, game_project_id: str) -> DesignAgentTraceResponse:
        run = self._get_run(db, run_id, game_project_id)
        rows = db.query(DesignAgentNodeExecution).filter(
            DesignAgentNodeExecution.run_id == run.id,
            DesignAgentNodeExecution.game_project_id == game_project_id,
        ).order_by(
            DesignAgentNodeExecution.started_at,
            DesignAgentNodeExecution.attempt,
        ).all()
        return DesignAgentTraceResponse(
            run_id=run.id,
            status=run.status,
            items=[DesignAgentTraceItem.model_validate(row) for row in rows],
        )

    def _final_blueprint(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
    ) -> tuple[DesignAgentRun, GameBlueprint, DesignAgentArtifact]:
        run = self._get_run(db, run_id, game_project_id)
        final_artifact = db.query(DesignAgentArtifact).filter(
            DesignAgentArtifact.run_id == run.id,
            DesignAgentArtifact.game_project_id == game_project_id,
            DesignAgentArtifact.artifact_type == "final",
            DesignAgentArtifact.immutable.is_(True),
        ).first()
        if final_artifact is None or final_artifact.blueprint_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approve and finalize the run before exporting it.",
            )
        blueprint = db.query(GameBlueprint).filter(
            GameBlueprint.id == final_artifact.blueprint_id,
            GameBlueprint.game_project_id == game_project_id,
        ).first()
        if blueprint is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The finalized blueprint snapshot is unavailable.",
            )
        return run, blueprint, final_artifact

    def technical_brief(self, db: Session, run_id: UUID, game_project_id: str) -> tuple[str, str]:
        run, blueprint, artifact = self._final_blueprint(db, run_id, game_project_id)
        snapshot = db.query(DesignAgentEvidenceSnapshot).filter(
            DesignAgentEvidenceSnapshot.id == artifact.evidence_snapshot_id,
            DesignAgentEvidenceSnapshot.run_id == run.id,
            DesignAgentEvidenceSnapshot.game_project_id == game_project_id,
        ).first()
        if snapshot is None:
            raise HTTPException(status_code=409, detail="The finalized design's frozen evidence is unavailable.")
        safe_name = "".join(
            character if character.isalnum() else "-"
            for character in blueprint.title.lower()
        ).strip("-")[:80]
        return (
            BlueprintBriefService().build(db, blueprint, game_project_id, frozen_context={
                "content": artifact.content, "evidence": snapshot.items or [],
                "decisions": (run.model_config or {}).get("resolved_decisions", []),
                "run_id": str(run.id), "artifact_id": str(artifact.id),
                "artifact_version": artifact.version, "snapshot_id": str(snapshot.id),
            }),
            f"{safe_name or 'gamemind-agent-brief'}.md",
        )

    def runtime_export(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
    ) -> DesignAgentRuntimeExportResponse:
        run, blueprint, artifact = self._final_blueprint(db, run_id, game_project_id)
        preview = artifact.content.get("unity_runtime_preview") or {}
        if (run.model_config or {}).get("defer_runtime") is True or preview.get("runtime_deferred") is True:
            raise HTTPException(status_code=409, detail="Runtime integration was explicitly deferred. Download the design brief; this run has no client-ready runtime export.")
        return DesignAgentRuntimeExportResponse(
            run_id=run.id,
            blueprint_id=blueprint.id,
            game_project_id=game_project_id,
            runtime_data=preview.get("content", {}),
        )
