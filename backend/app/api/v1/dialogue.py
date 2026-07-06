import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import (
    DialogueAssembleRequest, 
    DialogueAssembleResponse, 
    DialogueChatRequest, 
    DialogueChatResponse
)
from app.services.dialogue_service import DialogueService
from app.services.llm.factory import get_llm_provider, get_provider_name
from app.config import settings
from app.dependencies import get_game_project_id, get_player_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dialogue", tags=["dialogue"])

_LORE_TRIGGER_TERMS = {
    "who", "what", "where", "when", "why", "how", "tell", "explain", "describe",
    "king", "queen", "faction", "lore", "history", "quest", "objective", "place",
    "location", "world", "war", "siege", "npc", "character", "enemy", "ally",
    "remember", "memory", "frostpeak", "arven", "ember", "cinder", "vanguard",
}

_GREETING_ONLY_MESSAGES = {
    "hi", "hello", "hey", "hello there", "hi there", "hey there", "greetings",
    "good morning", "good afternoon", "good evening",
}


def _should_auto_retrieve_lore(message: str) -> bool:
    normalized = " ".join(message.lower().strip().split())
    if not normalized:
        return False
    if normalized in _GREETING_ONLY_MESSAGES:
        return False

    tokens = {
        token.strip(".,!?;:()[]{}\"'")
        for token in normalized.split()
        if token.strip(".,!?;:()[]{}\"'")
    }
    if len(tokens) <= 2 and not tokens.intersection(_LORE_TRIGGER_TERMS):
        return False
    return bool(tokens.intersection(_LORE_TRIGGER_TERMS) or "?" in normalized)


def _with_auto_retrieved_chunks(request: DialogueChatRequest, game_project_id: str) -> DialogueChatRequest:
    if request.selected_chunk_ids:
        return request
    if not _should_auto_retrieve_lore(request.player_message):
        return request

    try:
        from app.services.rag_service import RAGService

        rag_service = RAGService()
        results = rag_service.query_lore(
            query_text=request.player_message,
            limit=5,
            game_project_id=game_project_id,
        )
        chunk_ids = []
        for result in results:
            chunk_id = result.get("chunk_id")
            if not chunk_id:
                continue
            try:
                chunk_ids.append(UUID(str(chunk_id)))
            except ValueError:
                logger.warning("Skipping invalid auto-retrieved chunk id: %s", chunk_id)
        if not chunk_ids:
            return request
        return request.model_copy(update={"selected_chunk_ids": chunk_ids})
    except Exception as exc:
        logger.warning("Auto lore retrieval failed for dialogue chat: %s", exc)
        return request

@router.post("/assemble", response_model=DialogueAssembleResponse)
def assemble_dialogue(
    request: DialogueAssembleRequest, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """
    Assemble context parameters and the final prompt for dialogue simulation deterministically.
    """
    try:
        response = DialogueService.assemble_prompt(db, request, game_project_id=game_project_id)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dialogue assembly process failed: {str(e)}"
        )

@router.post("/chat", response_model=DialogueChatResponse)
async def chat_dialogue(
    request: DialogueChatRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    player_id: str = Depends(get_player_id)
):
    """
    Execute a live chat response generation using the configured LLM provider.
    """
    try:
        conv = None
        history = None
        request = _with_auto_retrieved_chunks(request, game_project_id)
        active_player_id = request.player_id or player_id
        if request.conversation_id:
            from app.models.session import Conversation, Message
            conv = db.query(Conversation).filter(
                Conversation.id == request.conversation_id,
                Conversation.game_project_id == game_project_id
            ).first()
            if not conv or conv.npc_slug != request.npc_slug:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation session not found or NPC slug mismatch."
                )
            
            # Fetch last 10 messages before adding the new one
            history = db.query(Message).filter(
                Message.conversation_id == request.conversation_id
            ).order_by(Message.created_at.desc()).limit(10).all()
            history.reverse()
            
            # Save player message
            player_msg_db = Message(
                conversation_id=request.conversation_id,
                sender="player",
                content=request.player_message
            )
            db.add(player_msg_db)
            db.flush()

        # 1. Assemble the prompt deterministically
        assembled = DialogueService.assemble_prompt(db, request, history=history, game_project_id=game_project_id)
        
        # 2. Instantiate provider from factory
        provider = get_llm_provider()
        
        # 3. Determine model to use
        model_name = request.model_override or settings.LOCAL_MODEL_NAME
        
        # 4. Construct the full system context (system prompt, NPC attributes, retrieved context)
        full_system_context = (
            f"{assembled.system_prompt}\n\n"
            f"[NPC Attributes]\n"
            f"{assembled.npc_context}\n\n"
            f"[LORE CONTEXT]\n"
            f"{assembled.retrieved_context}"
        )
        
        # 5. Call LLM provider
        response_text, telemetry = await provider.generate_response(
            system_prompt=full_system_context,
            user_prompt=assembled.player_message,
            max_output_tokens=400,
            model_name=model_name
        )
        
        # Record LLM call telemetry in database
        provider_type = get_provider_name(provider)
        from app.services.telemetry_service import TelemetryService
        TelemetryService.record_log(
            db=db,
            npc_slug=assembled.npc_slug,
            model_used=model_name,
            llm_provider=provider_type,
            latency_ms=telemetry.get("latency_ms", 0),
            action_type="dialogue",
            input_tokens=telemetry.get("input_tokens", 0),
            output_tokens=telemetry.get("output_tokens", 0),
            estimated_cost_usd=telemetry.get("estimated_cost_usd", 0.0),
            safety_blocked=telemetry.get("safety_blocked", False),
            safety_ratings=telemetry.get("safety_ratings", []),
            error=telemetry.get("error"),
            conversation_id=request.conversation_id
        )

        # Save NPC response if conversation exists
        if conv:
            from app.models.session import Message
            from sqlalchemy import func
            npc_msg_db = Message(
                conversation_id=conv.id,
                sender="npc",
                content=response_text
            )
            db.add(npc_msg_db)
            conv.updated_at = func.now()
            db.commit()

            # Check if summarization trigger is met
            all_messages = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at).all()
            
            unsummarized = []
            if conv.last_summarized_message_id:
                found_last = False
                for msg in all_messages:
                    if found_last:
                        unsummarized.append(msg)
                    elif msg.id == conv.last_summarized_message_id:
                        found_last = True
            else:
                unsummarized = all_messages
                
            unsummarized_count = len(unsummarized)
            unsummarized_chars = sum(len(msg.content) for msg in unsummarized)
            
            if unsummarized_count >= 10 or unsummarized_chars >= 6000:
                from app.services.rag_service import RAGService
                from app.services.memory_service import MemoryService
                
                rag = RAGService()
                mem_service = MemoryService(rag)
                
                background_tasks.add_task(
                    mem_service.run_summarization_and_promotion,
                    db,
                    conv.id
                )
        
        # 6. Combine warnings
        all_warnings = list(assembled.warnings)
        if telemetry.get("error"):
            all_warnings.append(f"LLM Provider Error: {telemetry['error']}")
            
        provider_type = get_provider_name(provider)

        # Resolve animations and emotions via Presentation Service
        from app.services.emotion_engine import EmotionEngine
        from app.services.runtime_presentation_service import RuntimePresentationService
        from app.models.npc import NPCProfile
        from app.services.rag_service import RAGService
        
        # 1. Fetch current emotional state
        emotions_raw = EmotionEngine.get_emotional_state(db, assembled.npc_slug, active_player_id, game_project_id=game_project_id)
        
        # 2. Get normalized emotions (0.0 - 1.0)
        normalized_emotions = RuntimePresentationService.get_normalized_emotions(emotions_raw)
        
        # 3. Determine dominant emotion & animation suggestions
        dominant = RuntimePresentationService.dominant_emotion(emotions_raw)
        npc = db.query(NPCProfile).filter(
            NPCProfile.slug == assembled.npc_slug,
            NPCProfile.game_project_id == game_project_id,
            NPCProfile.deleted_at.is_(None)
        ).first()
        animation_hints = npc.animation_hints if npc else None
        suggested_anim = RuntimePresentationService.resolve_animation(dominant, animation_hints)
        
        # 4. Resolve citations
        rag_service = RAGService()
        citations = RuntimePresentationService.resolve_citations(
            assembled.retrieved_chunks,
            request.player_message,
            rag_service,
            game_project_id,
            db
        )

        return DialogueChatResponse(
            api_version="1.0",
            npc_slug=assembled.npc_slug,
            response_text=response_text,
            suggested_animation=suggested_anim,
            npc_emotions=normalized_emotions,
            citations=citations,
            conversation_id=request.conversation_id,
            # Maintain backward compatibility
            prompt_version=request.prompt_version or "v1",
            model_used=model_name,
            llm_provider=provider_type,
            telemetry=telemetry,
            warnings=all_warnings
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Dialogue chat failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dialogue chat simulation failed: {str(e)}"
        )
