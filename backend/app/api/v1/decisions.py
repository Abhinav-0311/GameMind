from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_game_project_id
from app.schemas import DecisionCoverageResponse, DesignDecisionResponse
from app.services.design_decision_service import DesignDecisionService

router = APIRouter(prefix="/decisions", tags=["decisions"])


class DecisionSyncRequest(BaseModel):
    document_id: UUID


class DecisionUpdateRequest(BaseModel):
    decision: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[str] = Field(default=None, pattern="^(open|resolved)$")


class DecisionEvidenceRequest(BaseModel):
    evidence_document_id: UUID


@router.get("/", response_model=List[DesignDecisionResponse])
def list_decisions(
    document_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    return DesignDecisionService().list_for_document(db, document_id, game_project_id)


@router.post("/sync", response_model=List[DesignDecisionResponse])
def sync_decisions(
    request: DecisionSyncRequest,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Create or refresh open decision records from the selected source review."""
    return DesignDecisionService().sync_from_review(db, request.document_id, game_project_id)


@router.get("/coverage", response_model=DecisionCoverageResponse)
def get_decision_coverage(
    document_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Show whether decisions from this source lineage have evidence in this revision."""
    return DesignDecisionService().coverage(db, document_id, game_project_id)


@router.put("/{decision_id}", response_model=DesignDecisionResponse)
def update_decision(
    decision_id: UUID,
    request: DecisionUpdateRequest,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    return DesignDecisionService().update(db, decision_id, game_project_id, request.decision, request.status)


@router.put("/{decision_id}/evidence", response_model=DesignDecisionResponse)
def attach_decision_evidence(
    decision_id: UUID,
    request: DecisionEvidenceRequest,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Attach a project-owned supporting source without silently resolving the decision."""
    return DesignDecisionService().attach_evidence(
        db,
        decision_id,
        request.evidence_document_id,
        game_project_id,
    )
