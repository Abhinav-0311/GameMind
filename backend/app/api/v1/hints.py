import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import HintGenerateRequest, HintResponse, HintStatusResponse
from app.services.hint_engine import HintEngine, HINT_COOLDOWN_SECONDS
from app.dependencies import get_game_project_id

logger = logging.getLogger("gamemind.api.hints")

router = APIRouter(prefix="/hints", tags=["hints"])

@router.post("/generate", response_model=HintResponse, status_code=status.HTTP_200_OK)
async def generate_hint(
    request: HintGenerateRequest, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """
    Generate progressive hints (Level 1 subtle, Level 2 medium, Level 3 direct).
    Enforces sequential progression rules and request cooldowns.
    """
    try:
        hint_data = await HintEngine.generate_hint(
            db=db,
            quest_id=request.quest_id,
            player_id=request.player_id,
            hint_level=request.hint_level,
            game_project_id=game_project_id
        )
        return hint_data
    except ValueError as val_err:
        logger.warning(f"Validation error generating hint: {val_err}")
        # Always return HTTP 422 for progressive hint validation failures
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Failed to generate hint: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(exc)}"
        )

@router.get("/status", response_model=HintStatusResponse, status_code=status.HTTP_200_OK)
def get_hint_status(
    quest_id: uuid.UUID, 
    player_id: str, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """
    Retrieve current progression level, last request time, and remaining cooldown.
    """
    try:
        current_level, last_requested = HintEngine.get_progression_state(
            db, player_id, quest_id, game_project_id=game_project_id
        )
        
        # Calculate remaining cooldown seconds
        cooldown_remaining = 0
        if last_requested:
            # Enforce timezone aware datetime comparison
            if last_requested.tzinfo is None:
                last_requested = last_requested.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            elapsed = (now - last_requested).total_seconds()
            if elapsed < HINT_COOLDOWN_SECONDS:
                cooldown_remaining = int(HINT_COOLDOWN_SECONDS - elapsed)

        return HintStatusResponse(
            quest_id=quest_id,
            player_id=player_id,
            current_level=current_level,
            last_requested_at=last_requested,
            cooldown_remaining_seconds=cooldown_remaining
        )
    except Exception as exc:
        logger.error(f"Failed to query hint status: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(exc)}"
        )
