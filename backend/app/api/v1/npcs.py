from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from app.database import get_db
from app.models.npc import NPCProfile
from app.schemas import NPCProfileCreate, NPCProfileUpdate, NPCProfileResponse
from app.dependencies import get_game_project_id
from uuid import UUID
from typing import List

router = APIRouter(prefix="/npcs", tags=["npcs"])

@router.post("", response_model=NPCProfileResponse, status_code=status.HTTP_201_CREATED)
def create_npc(
    npc_in: NPCProfileCreate, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Create a new NPC profile. Validates slug uniqueness within project."""
    # Check if slug already exists in this project
    existing_npc = db.query(NPCProfile).filter(
        NPCProfile.slug == npc_in.slug,
        NPCProfile.game_project_id == game_project_id
    ).first()
    if existing_npc:
        if existing_npc.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"NPC with slug '{npc_in.slug}' already exists (soft-deleted)."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"NPC with slug '{npc_in.slug}' already exists."
            )

    db_npc = NPCProfile(
        slug=npc_in.slug,
        name=npc_in.name,
        title=npc_in.title,
        personality_summary=npc_in.personality_summary,
        dialogue_style=npc_in.dialogue_style,
        voice_profile=npc_in.voice_profile,
        faction_alignment=npc_in.faction_alignment,
        animation_hints=npc_in.animation_hints,
        memory_settings=npc_in.memory_settings,
        metadata_json=npc_in.metadata,
        game_project_id=game_project_id
    )

    db.add(db_npc)
    try:
        db.commit()
        db.refresh(db_npc)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error: Slug must be unique."
        )
    return db_npc

@router.get("", response_model=List[NPCProfileResponse])
def list_npcs(
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """List all NPC profiles excluding soft-deleted ones."""
    return db.query(NPCProfile).filter(
        NPCProfile.deleted_at.is_(None),
        NPCProfile.game_project_id == game_project_id
    ).all()

@router.get("/{id}", response_model=NPCProfileResponse)
def get_npc(
    id: UUID, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Fetch an NPC profile by ID. Excludes soft-deleted ones (returns 404)."""
    npc = db.query(NPCProfile).filter(
        NPCProfile.id == id, 
        NPCProfile.game_project_id == game_project_id,
        NPCProfile.deleted_at.is_(None)
    ).first()
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NPC profile not found or has been deleted."
        )
    return npc

@router.put("/{id}", response_model=NPCProfileResponse)
def update_npc(
    id: UUID, 
    npc_in: NPCProfileUpdate, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Update an active NPC profile fields and maintain updated_at."""
    npc = db.query(NPCProfile).filter(
        NPCProfile.id == id, 
        NPCProfile.game_project_id == game_project_id,
        NPCProfile.deleted_at.is_(None)
    ).first()
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NPC profile not found or has been deleted."
        )

    # Dump fields that were set in the update request
    update_data = npc_in.model_dump(exclude_unset=True) if hasattr(npc_in, "model_dump") else npc_in.dict(exclude_unset=True)
    
    # Handle alias mapping for metadata -> metadata_json
    if "metadata" in update_data:
        update_data["metadata_json"] = update_data.pop("metadata")

    for key, value in update_data.items():
        setattr(npc, key, value)

    npc.updated_at = func.now()
    db.commit()
    db.refresh(npc)
    return npc

@router.delete("/{id}")
def delete_npc(
    id: UUID, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Soft delete an NPC profile by setting deleted_at timestamp."""
    npc = db.query(NPCProfile).filter(
        NPCProfile.id == id, 
        NPCProfile.game_project_id == game_project_id,
        NPCProfile.deleted_at.is_(None)
    ).first()
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NPC profile not found or has been deleted."
        )
    npc.deleted_at = func.now()
    db.commit()
    return {"status": "success", "message": "NPC profile soft-deleted successfully.", "id": str(id)}
