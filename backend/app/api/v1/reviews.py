from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_game_project_id
from app.schemas import GddReviewResponse
from app.services.gdd_review_service import GddReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/documents/{document_id}", response_model=GddReviewResponse)
def review_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Review a source GDD for explicit design decisions and clear scope conflicts."""
    return GddReviewService().review(db, document_id, game_project_id)
