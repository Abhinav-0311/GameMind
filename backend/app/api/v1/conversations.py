from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.npc import NPCProfile
from app.models.session import Conversation
from app.schemas import ConversationCreate, ConversationResponse, ConversationDetailResponse
from uuid import UUID
from typing import List, Optional

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    """Create a new conversation session associated with an NPC slug."""
    npc = db.query(NPCProfile).filter(
        NPCProfile.slug == payload.npc_slug,
        NPCProfile.deleted_at.is_(None)
    ).first()

    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC profile with slug '{payload.npc_slug}' not found or has been deleted."
        )

    db_conv = Conversation(
        npc_id=npc.id,
        npc_slug=npc.slug,
        title=f"Conversation with {npc.name}",
        status="active"
    )

    db.add(db_conv)
    db.commit()
    db.refresh(db_conv)
    return db_conv

@router.get("", response_model=List[ConversationResponse])
def list_conversations(npc_slug: Optional[str] = None, db: Session = Depends(get_db)):
    """List all active conversation sessions, optionally filtered by NPC slug."""
    query = db.query(Conversation)
    if npc_slug:
        query = query.filter(Conversation.npc_slug == npc_slug)
    return query.order_by(Conversation.updated_at.desc()).all()

@router.get("/{id}", response_model=ConversationDetailResponse)
def get_conversation(id: UUID, db: Session = Depends(get_db)):
    """Retrieve details and chronological messages for a specific conversation session."""
    conv = db.query(Conversation).filter(Conversation.id == id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation session not found."
        )
    return conv

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(id: UUID, db: Session = Depends(get_db)):
    """Permanently delete a conversation session and cascade delete all associated messages."""
    conv = db.query(Conversation).filter(Conversation.id == id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation session not found."
        )
    db.delete(conv)
    db.commit()
    return
