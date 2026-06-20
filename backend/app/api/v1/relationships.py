from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.npc import NPCProfile
from app.models.relationship import NPCRelationship
from app.schemas import NPCRelationshipResponse, NPCRelationshipUpdate
from app.services.dialogue_service import DialogueService
from typing import List, Optional

router = APIRouter(prefix="/relationships", tags=["relationships"])

def serialize_relationship(rel: NPCRelationship) -> dict:
    standing = DialogueService.get_standing_label(
        rel.trust, rel.respect, rel.friendship, rel.fear
    )
    return {
        "id": rel.id,
        "player_id": rel.player_id,
        "npc_slug": rel.npc_slug,
        "trust": rel.trust,
        "respect": rel.respect,
        "friendship": rel.friendship,
        "fear": rel.fear,
        "last_reason": rel.last_reason,
        "updated_at": rel.updated_at,
        "standing": standing
    }

@router.get("", response_model=List[NPCRelationshipResponse])
def get_relationships(
    npc_slug: Optional[str] = None,
    player_id: Optional[str] = "default_player",
    db: Session = Depends(get_db)
):
    """Retrieve standings list, optionally filtered by npc_slug and player_id."""
    try:
        query = db.query(NPCRelationship)
        if npc_slug:
            query = query.filter(NPCRelationship.npc_slug == npc_slug)
        if player_id:
            query = query.filter(NPCRelationship.player_id == player_id)
        
        rels = query.all()
        return [serialize_relationship(r) for r in rels]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve relationships: {e}"
        )

@router.post("/update", response_model=NPCRelationshipResponse)
def update_relationship(payload: NPCRelationshipUpdate, db: Session = Depends(get_db)):
    """Create or update NPC relationship values for a specific player."""
    # Verify NPC slug exists
    npc = db.query(NPCProfile).filter(
        NPCProfile.slug == payload.npc_slug,
        NPCProfile.deleted_at.is_(None)
    ).first()
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active NPC profile with slug '{payload.npc_slug}' not found."
        )

    try:
        player_id = payload.player_id or "default_player"
        rel = db.query(NPCRelationship).filter(
            NPCRelationship.npc_slug == payload.npc_slug,
            NPCRelationship.player_id == player_id
        ).first()

        if not rel:
            import uuid
            rel = NPCRelationship(
                id=uuid.uuid4(),
                player_id=player_id,
                npc_slug=payload.npc_slug,
                trust=payload.trust if payload.trust is not None else 50,
                respect=payload.respect if payload.respect is not None else 50,
                friendship=payload.friendship if payload.friendship is not None else 50,
                fear=payload.fear if payload.fear is not None else 0,
                last_reason=payload.last_reason
            )
            db.add(rel)
        else:
            if payload.trust is not None:
                rel.trust = payload.trust
            if payload.respect is not None:
                rel.respect = payload.respect
            if payload.friendship is not None:
                rel.friendship = payload.friendship
            if payload.fear is not None:
                rel.fear = payload.fear
            if payload.last_reason is not None:
                rel.last_reason = payload.last_reason
                
        db.commit()
        db.refresh(rel)
        return serialize_relationship(rel)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update relationship: {e}"
        )
