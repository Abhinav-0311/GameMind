from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_game_project_id
from app.design_agent.schemas import (
    DesignAgentEvaluationCreate,
    DesignAgentEvaluationResponse,
    DesignAgentReviewRequest,
    DesignAgentRunCreate,
    DesignAgentRunResponse,
    DesignAgentRuntimeExportResponse,
    DesignAgentTraceResponse,
)
from app.design_agent.evaluation import DesignAgentEvaluationService
from app.design_agent.service import DesignAgentService
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
    """Start a durable design workflow and pause at its first human review."""
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
    )


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
