from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_game_project_id
from app.design_agent.schemas import (
    DesignAgentFindingResolutionCreate,
    DesignAgentFindingResolutionResponse,
    DesignAgentFindingReviewResponse,
    DesignAgentEvaluationCreate,
    DesignAgentEvaluationResponse,
    DesignAgentEvidenceResponse,
    DesignAgentCritiqueRetryRequest,
    DesignAgentReviewRequest,
    DesignAgentRunCreate,
    DesignAgentRunResponse,
    DesignAgentRuntimeExportResponse,
    DesignAgentTraceResponse,
)
from app.design_agent.evaluation import DesignAgentEvaluationService
from app.design_agent.service import DesignAgentService
from app.design_agent.finding_reviews import DesignFindingReviewService
from app.models.user import User

router = APIRouter(prefix="/design-agent", tags=["design-agent"])


def get_design_agent_service() -> DesignAgentService:
    return DesignAgentService()


def get_design_agent_evaluation_service() -> DesignAgentEvaluationService:
    return DesignAgentEvaluationService()


@router.post("/runs", response_model=DesignAgentRunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: DesignAgentRunCreate,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    current_user: User | None = Depends(get_current_user),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    """Start a durable workflow; inline failure returns 503 detail {message, run_id}."""
    return service.create_and_start(db, payload, game_project_id, current_user)


@router.get("/runs", response_model=list[DesignAgentRunResponse])
def list_runs(
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    return service.list_runs(db, game_project_id)


@router.get("/runs/{run_id}", response_model=DesignAgentRunResponse)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    return service.get_run(db, run_id, game_project_id)


@router.get("/runs/{run_id}/artifacts/{artifact_id}/evidence", response_model=DesignAgentEvidenceResponse)
def get_artifact_evidence(
    run_id: UUID,
    artifact_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    return service.get_artifact_evidence(db, run_id, artifact_id, game_project_id)


@router.post("/runs/{run_id}/retry-critique", response_model=DesignAgentRunResponse)
def retry_critique(
    run_id: UUID,
    payload: DesignAgentCritiqueRetryRequest,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    current_user: User | None = Depends(get_current_user),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    return service.retry_critique(db, run_id, game_project_id, payload, current_user)


@router.post("/runs/{run_id}/review", response_model=DesignAgentRunResponse)
def review_run(
    run_id: UUID,
    payload: DesignAgentReviewRequest,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    current_user: User | None = Depends(get_current_user),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    """Resume a paused graph with an auditable approve or reject decision."""
    return service.review(
        db,
        run_id,
        game_project_id,
        payload.decision,
        payload.reason,
        current_user,
        target_sections=payload.target_sections,
        artifact_id=payload.artifact_id,
        confirmed_proposals=[item.model_dump() for item in payload.confirmed_proposals],
        acknowledge_degraded=payload.acknowledge_degraded,
        target_paths=payload.target_paths,
    )


@router.get("/runs/{run_id}/artifacts/{artifact_id}/finding-resolutions", response_model=DesignAgentFindingReviewResponse)
def list_finding_resolutions(
    run_id: UUID, artifact_id: UUID, db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    current_user: User | None = Depends(get_current_user),
):
    """Read raw findings and separate human audit records; no approval effect."""
    return DesignFindingReviewService().list(db, run_id, artifact_id, game_project_id, current_user)


@router.post("/runs/{run_id}/artifacts/{artifact_id}/finding-resolutions",
             response_model=DesignAgentFindingResolutionResponse, status_code=status.HTTP_201_CREATED)
def record_finding_resolution(
    run_id: UUID, artifact_id: UUID, payload: DesignAgentFindingResolutionCreate,
    db: Session = Depends(get_db), game_project_id: str = Depends(get_game_project_id),
    current_user: User | None = Depends(get_current_user),
):
    """Record a human dispute only. Does not approve, resume, revise or call a provider."""
    return DesignFindingReviewService().create(db, run_id, artifact_id, game_project_id, payload, current_user)


@router.get("/runs/{run_id}/trace", response_model=DesignAgentTraceResponse)
def get_trace(
    run_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    return service.trace(db, run_id, game_project_id)


@router.get(
    "/runs/{run_id}/evaluation",
    response_model=DesignAgentEvaluationResponse,
)
def get_evaluation(
    run_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    service: DesignAgentEvaluationService = Depends(
        get_design_agent_evaluation_service
    ),
):
    return service.get(db, run_id, game_project_id)


@router.post(
    "/runs/{run_id}/evaluation",
    response_model=DesignAgentEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation(
    run_id: UUID,
    payload: DesignAgentEvaluationCreate,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    current_user: User | None = Depends(get_current_user),
    service: DesignAgentEvaluationService = Depends(
        get_design_agent_evaluation_service
    ),
):
    """Record one immutable, human-reviewed quality scorecard."""
    return service.create(db, run_id, game_project_id, payload, current_user)


@router.get("/runs/{run_id}/exports/technical-brief")
def export_technical_brief(
    run_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    content, filename = service.technical_brief(db, run_id, game_project_id)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/runs/{run_id}/exports/runtime",
    response_model=DesignAgentRuntimeExportResponse,
)
def export_runtime(
    run_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    service: DesignAgentService = Depends(get_design_agent_service),
):
    return service.runtime_export(db, run_id, game_project_id)
