from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.npc import NPCProfile
from app.schemas import NPCMemoryCreate, NPCMemoryResponse, MemoryConsolidateRequest, MemoryConsolidateResponse
from app.services.rag_service import RAGService
from app.services.memory_service import MemoryService
from app.dependencies import get_game_project_id
from uuid import UUID
from typing import List, Optional

router = APIRouter(prefix="/memories", tags=["memories"])

def get_memory_service():
    rag = RAGService()
    return MemoryService(rag)

@router.post("", response_model=NPCMemoryResponse, status_code=status.HTTP_201_CREATED)
def create_npc_memory(
    payload: NPCMemoryCreate,
    db: Session = Depends(get_db),
    mem_service: MemoryService = Depends(get_memory_service),
    game_project_id: str = Depends(get_game_project_id)
):
    """Create a new NPC memory in PostgreSQL first, and attempt Chroma vector indexing."""
    npc = db.query(NPCProfile).filter(
        NPCProfile.slug == payload.npc_slug,
        NPCProfile.game_project_id == game_project_id,
        NPCProfile.deleted_at.is_(None)
    ).first()

    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC profile with slug '{payload.npc_slug}' not found or has been deleted."
        )

    # If conversation_id is provided, verify it exists
    if payload.conversation_id:
        from app.models.session import Conversation
        conv = db.query(Conversation).filter(
            Conversation.id == payload.conversation_id,
            Conversation.game_project_id == game_project_id
        ).first()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation session with ID '{payload.conversation_id}' not found."
            )

    try:
        memory = mem_service.create_memory(
            db=db,
            npc_id=npc.id,
            memory_text=payload.memory_text,
            memory_type=payload.memory_type,
            importance_score=payload.importance_score,
            conversation_id=payload.conversation_id,
            game_project_id=game_project_id
        )
        return memory
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating memory: {e}"
        )

@router.post("/sync")
def sync_memories(
    db: Session = Depends(get_db),
    mem_service: MemoryService = Depends(get_memory_service)
):
    """Trigger manual re-indexing of unindexed PostgreSQL memories into Chroma DB."""
    try:
        result = mem_service.sync_unindexed_memories(db)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during memory synchronization: {e}"
        )

@router.post("/consolidate", response_model=MemoryConsolidateResponse)
def consolidate_memories_endpoint(
    payload: MemoryConsolidateRequest,
    db: Session = Depends(get_db),
    mem_service: MemoryService = Depends(get_memory_service),
    game_project_id: str = Depends(get_game_project_id)
):
    """Trigger semantic cluster-based duplicate consolidation for an NPC's memories."""
    try:
        result = mem_service.consolidate_memories(db, payload.npc_slug, game_project_id=game_project_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during memory consolidation: {e}"
        )
