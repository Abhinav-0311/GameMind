from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.world_state import WorldStateFlag
from app.schemas import WorldStateFlagResponse, WorldStateFlagToggle
from typing import List

router = APIRouter(prefix="/world-state", tags=["world-state"])

@router.get("", response_model=List[WorldStateFlagResponse])
def get_world_state(db: Session = Depends(get_db)):
    """Fetch all world state flags ordered by priority DESC, updated_at DESC."""
    try:
        flags = db.query(WorldStateFlag).order_by(
            WorldStateFlag.priority.desc(),
            WorldStateFlag.updated_at.desc()
        ).all()
        return flags
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve world state: {e}"
        )

@router.post("/toggle", response_model=WorldStateFlagResponse)
def toggle_world_state(payload: WorldStateFlagToggle, db: Session = Depends(get_db)):
    """Explicitly create or update a world state flag's value and is_active status."""
    try:
        flag = db.query(WorldStateFlag).filter(WorldStateFlag.flag_key == payload.flag_key).first()
        if not flag:
            flag = WorldStateFlag(
                flag_key=payload.flag_key,
                flag_value=payload.flag_value,
                is_active=payload.is_active,
                priority=payload.priority or 0
            )
            db.add(flag)
        else:
            flag.flag_value = payload.flag_value
            flag.is_active = payload.is_active
            if payload.priority is not None:
                flag.priority = payload.priority
        db.commit()
        db.refresh(flag)
        return flag
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update world state flag: {e}"
        )
