from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.design_agent.contracts import ResumeDecision
from app.design_agent.provider_factory import build_design_agent_provider
from app.design_agent.schemas import (
    DesignAgentArtifactResponse,
    DesignAgentCritiqueResponse,
    DesignAgentRunCreate,
    DesignAgentRunResponse,
    DesignAgentRuntimeExportResponse,
    DesignAgentTraceItem,
    DesignAgentTraceResponse,
)
from app.design_agent.workflow import DesignAgentWorkflow
from app.models.blueprint import GameBlueprint
from app.models.design_agent import (
    DesignAgentArtifact,
    DesignAgentCritique,
    DesignAgentNodeExecution,
    DesignAgentRun,
)
from app.models.document import Document
from app.models.user import User
from app.services.blueprint_brief_service import BlueprintBriefService


class DesignAgentService:
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
        critique = db.query(DesignAgentCritique).filter(
            DesignAgentCritique.run_id == run.id,
            DesignAgentCritique.game_project_id == run.game_project_id,
        ).order_by(DesignAgentCritique.created_at.desc()).first()
        return DesignAgentRunResponse(
            id=run.id,
            game_project_id=run.game_project_id,
            objective=run.objective,
            document_ids=[str(document_id) for document_id in run.document_ids],
            status=run.status,
            current_node=run.current_node,
            provider_name=run.provider_name,
            degraded=bool((run.model_config or {}).get("degraded")),
            retrieval_revision=run.retrieval_revision,
            revision_count=run.revision_count,
            max_revisions=run.max_revisions,
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

        run = DesignAgentRun(
            game_project_id=game_project_id,
            created_by_user_id=current_user.id if current_user else None,
            objective=payload.objective.strip(),
            document_ids=[str(document_id) for document_id in document_ids],
            provider_name=self.workflow.provider.name,
            model_config={
                "phase": "phase_2",
                **self.workflow.provider.configuration(),
                "degraded": False,
            },
            max_revisions=payload.max_revisions,
        )
        db.add(run)
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
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The design-agent workflow could not start. Inspect the run trace for details.",
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

    def review(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
        decision: str,
        reason: str | None,
        current_user: User | None,
    ) -> DesignAgentRunResponse:
        run = self._get_run(db, run_id, game_project_id)
        if run.status != "awaiting_review":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This run cannot be reviewed while its status is '{run.status}'.",
            )
        try:
            self.workflow.resume(
                run.id,
                ResumeDecision(
                    decision=decision,
                    reason=reason.strip() if reason else None,
                    reviewer_user_id=str(current_user.id) if current_user else None,
                    reviewer_label=current_user.email if current_user else "local_developer",
                ),
            )
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The design-agent workflow could not resume. Inspect the run trace for details.",
            ) from error
        db.expire_all()
        return self._response(db, self._get_run(db, run_id, game_project_id))

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
            items=[
                DesignAgentTraceItem(
                    id=row.id,
                    node_name=row.node_name,
                    attempt=row.attempt,
                    status=row.status,
                    provider_name=row.provider_name,
                    model_name=row.model_name,
                    latency_ms=row.latency_ms,
                    input_tokens=row.input_tokens,
                    output_tokens=row.output_tokens,
                    cost_usd=float(row.cost_usd),
                    details=row.details,
                    error=row.error,
                    started_at=row.started_at,
                    completed_at=row.completed_at,
                )
                for row in rows
            ],
        )

    def _final_blueprint(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
    ) -> tuple[DesignAgentRun, GameBlueprint]:
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
        return run, blueprint

    def technical_brief(self, db: Session, run_id: UUID, game_project_id: str) -> tuple[str, str]:
        _run, blueprint = self._final_blueprint(db, run_id, game_project_id)
        safe_name = "".join(
            character if character.isalnum() else "-"
            for character in blueprint.title.lower()
        ).strip("-")[:80]
        return (
            BlueprintBriefService().build(db, blueprint, game_project_id),
            f"{safe_name or 'gamemind-agent-brief'}.md",
        )

    def runtime_export(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
    ) -> DesignAgentRuntimeExportResponse:
        run, blueprint = self._final_blueprint(db, run_id, game_project_id)
        return DesignAgentRuntimeExportResponse(
            run_id=run.id,
            blueprint_id=blueprint.id,
            game_project_id=game_project_id,
            runtime_data=(blueprint.unity_runtime_preview or {}).get("content", {}),
        )
