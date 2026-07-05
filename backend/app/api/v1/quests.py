import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective, QuestProgress
from app.schemas import (
    QuestCreate, QuestResponse, QuestProgressCreate,
    QuestProgressResponse, QuestProgressUpdate,
    QuestGenerateRequest, QuestValidateRequest, QuestValidationResponse,
    QuestGeneratedResponse
)
from app.dependencies import get_game_project_id, get_player_id
from app.services.rag_service import RAGService
from app.services.memory_service import MemoryService
from app.services.dynamic_quest_generator import DynamicQuestGenerator
from app.services.quest_template_engine import QuestTemplateEngine
from app.services.quest_validation_engine import QuestValidationEngine
from app.models.quest import GeneratedQuest
from sqlalchemy.sql import func
from sqlalchemy import desc
from typing import Dict, Any

import logging

router = APIRouter(prefix="/quests", tags=["quests"])
logger = logging.getLogger(__name__)

@router.post("", response_model=QuestResponse, status_code=status.HTTP_201_CREATED)
def create_quest(
    payload: QuestCreate, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    # Verify NPC exists
    npc = db.query(NPCProfile).filter(
        NPCProfile.slug == payload.npc_slug, 
        NPCProfile.game_project_id == game_project_id,
        NPCProfile.deleted_at.is_(None)
    ).first()
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC with slug '{payload.npc_slug}' not found or is deleted."
        )

    # Create Quest
    quest_id = uuid.uuid4()
    db_quest = Quest(
        id=quest_id,
        npc_slug=payload.npc_slug,
        title=payload.title,
        description=payload.description,
        difficulty=payload.difficulty,
        gold_reward=payload.gold_reward,
        xp_reward=payload.xp_reward,
        item_rewards=payload.item_rewards,
        game_project_id=game_project_id
    )
    db.add(db_quest)

    # Create Objectives
    db_objectives = []
    for obj in payload.objectives:
        db_obj = QuestObjective(
            id=uuid.uuid4(),
            quest_id=quest_id,
            objective_index=obj.objective_index,
            description=obj.description,
            target_type=obj.target_type,
            target_id=obj.target_id,
            quantity_required=obj.quantity_required
        )
        db.add(db_obj)
        db_objectives.append(db_obj)

    db.commit()
    db.refresh(db_quest)
    
    # Attach objectives to return matching schema validator
    db_quest.objectives = db_objectives
    return db_quest

@router.get("", response_model=List[QuestResponse])
def get_quests(
    npc_slug: Optional[str] = None, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    query = db.query(Quest).filter(Quest.game_project_id == game_project_id)
    if npc_slug:
        query = query.filter(Quest.npc_slug == npc_slug)
    quests = query.all()

    # Prefetch objectives to avoid N+1 query issue in model serializer
    for q in quests:
        q.objectives = db.query(QuestObjective).filter(QuestObjective.quest_id == q.id).order_by(QuestObjective.objective_index).all()
    
    return quests

@router.post("/progress", response_model=QuestProgressResponse, status_code=status.HTTP_201_CREATED)
def accept_quest(
    payload: QuestProgressCreate, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    player_id: str = Depends(get_player_id)
):
    active_player_id = payload.player_id or player_id

    # Check if quest exists
    quest = db.query(Quest).filter(
        Quest.id == payload.quest_id,
        Quest.game_project_id == game_project_id
    ).first()
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quest with ID '{payload.quest_id}' not found in this project."
        )

    # Check if player already has progress on this quest
    existing = db.query(QuestProgress).filter(
        QuestProgress.player_id == active_player_id,
        QuestProgress.quest_id == payload.quest_id,
        QuestProgress.game_project_id == game_project_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Player has already accepted or completed this quest."
        )

    # Get objectives for quest to initialize state
    objectives = db.query(QuestObjective).filter(QuestObjective.quest_id == quest.id).all()
    initial_state = {str(obj.objective_index): 0 for obj in objectives}

    db_progress = QuestProgress(
        id=uuid.uuid4(),
        player_id=active_player_id,
        quest_id=payload.quest_id,
        quest_giver_slug=quest.npc_slug,
        status="active",
        objectives_state=initial_state,
        game_project_id=game_project_id
    )
    db.add(db_progress)
    db.commit()
    db.refresh(db_progress)

    return db_progress


@router.get("/progress", response_model=List[QuestProgressResponse])
def get_quest_progress(
    player_id: Optional[str] = "default_player",
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    header_player_id: str = Depends(get_player_id)
):
    pid = player_id or header_player_id
    query = db.query(QuestProgress).filter(
        QuestProgress.player_id == pid,
        QuestProgress.game_project_id == game_project_id
    )
    if status:
        query = query.filter(QuestProgress.status == status)
    return query.all()

@router.post("/progress/update", response_model=QuestProgressResponse)
def update_quest_progress(
    payload: QuestProgressUpdate, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    player_id: str = Depends(get_player_id)
):
    active_player_id = payload.player_id or player_id

    # Get progress record
    progress = db.query(QuestProgress).filter(
        QuestProgress.player_id == active_player_id,
        QuestProgress.quest_id == payload.quest_id,
        QuestProgress.game_project_id == game_project_id
    ).first()

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest progress record not found for this player."
        )

    if progress.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update progress. Quest status is '{progress.status}'."
        )

    # Fetch quest and objectives to validate objective_index
    quest = db.query(Quest).filter(
        Quest.id == payload.quest_id,
        Quest.game_project_id == game_project_id
    ).first()
    objectives = db.query(QuestObjective).filter(QuestObjective.quest_id == payload.quest_id).all()
    obj_map = {obj.objective_index: obj for obj in objectives}

    if payload.objective_index not in obj_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Objective index {payload.objective_index} does not exist for this quest."
        )

    # Update objectives state
    idx_str = str(payload.objective_index)
    current_val = progress.objectives_state.get(idx_str, 0)
    new_val = current_val + payload.increment_amount
    
    # We shouldn't exceed quantity_required, but let's cap it or just set it
    req_val = obj_map[payload.objective_index].quantity_required
    if new_val > req_val:
        new_val = req_val

    # sqlalchemy needs explicit assignment for JSONB mutation detection or flag it
    new_state = dict(progress.objectives_state)
    new_state[idx_str] = new_val
    progress.objectives_state = new_state

    # Check if quest completed
    completed = True
    for obj in objectives:
        curr = progress.objectives_state.get(str(obj.objective_index), 0)
        if curr < obj.quantity_required:
            completed = False
            break

    if completed:
        progress.status = "completed"
        progress.completed_at = func.now()

        # Trigger NPC Memory Creation
        try:
            npc = db.query(NPCProfile).filter(
                NPCProfile.slug == quest.npc_slug, 
                NPCProfile.game_project_id == game_project_id,
                NPCProfile.deleted_at.is_(None)
            ).first()
            if npc:
                rag = RAGService()
                mem_service = MemoryService(rag)
                
                memory_text = f"Player successfully completed quest: {quest.title}"
                metadata = {
                    "type": "quest_completion",
                    "quest_id": str(quest.id),
                    "quest_title": quest.title,
                    "npc_slug": quest.npc_slug
                }
                mem_service.create_memory(
                    db=db,
                    npc_id=npc.id,
                    memory_text=memory_text,
                    memory_type="episodic",
                    importance_score=8.0,
                    metadata=metadata,
                    game_project_id=game_project_id
                )
                logger.info(f"Quest completion memory created for NPC {quest.npc_slug}.")
        except Exception as e:
            logger.error(f"Failed to generate quest completion memory: {e}")

    db.commit()
    db.refresh(progress)
    return progress


@router.post("/generate", response_model=QuestGeneratedResponse, status_code=status.HTTP_200_OK)
def generate_quest(
    payload: QuestGenerateRequest, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    player_id: str = Depends(get_player_id)
):
    active_player_id = payload.player_id or player_id
    # Verify NPC exists or raise 422
    npc = db.query(NPCProfile).filter(
        NPCProfile.slug == payload.npc_slug, 
        NPCProfile.game_project_id == game_project_id,
        NPCProfile.deleted_at.is_(None)
    ).first()
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"NPC with slug '{payload.npc_slug}' does not exist in this project."
        )
    try:
        quest = DynamicQuestGenerator.generate_quest(
            db=db,
            npc_slug=payload.npc_slug,
            player_id=active_player_id,
            player_level=payload.player_level,
            game_project_id=game_project_id
        )
        
        mapped_objectives = []
        for obj in quest["objectives"]:
            mapped_objectives.append({
                "id": uuid.uuid4(),
                "objective_index": obj["objective_index"],
                "description": obj["description"],
                "target_type": obj["target_type"],
                "target_id": obj["target_id"],
                "quantity_required": obj["quantity_required"]
            })
        
        rewards_raw = quest["rewards"]
        rewards_dto = {
            "gold": rewards_raw.get("gold", 0),
            "xp": rewards_raw.get("xp", 0),
            "items": rewards_raw.get("items", [])
        }
        
        return QuestGeneratedResponse(
            api_version="1.0",
            npc_slug=quest["npc_slug"],
            title=quest["title"],
            description=quest["description"],
            difficulty=quest["difficulty"],
            rewards=rewards_dto,
            objectives=mapped_objectives
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post("/validate", response_model=QuestValidationResponse, status_code=status.HTTP_200_OK)
def validate_quest(
    payload: QuestValidateRequest, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    # If objectives count > 10 or rewards > 5, we raise 422:
    if len(payload.objectives) > 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Objectives count cannot exceed 10."
        )
    reward_count = 0
    if payload.rewards.get("gold", 0) > 0:
        reward_count += 1
    if payload.rewards.get("xp", 0) > 0:
        reward_count += 1
    reward_count += len(payload.rewards.get("items", []))

    if reward_count > 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rewards count cannot exceed 5."
        )

    if payload.npc_slug:
        npc = db.query(NPCProfile).filter(
            NPCProfile.slug == payload.npc_slug, 
            NPCProfile.game_project_id == game_project_id,
            NPCProfile.deleted_at.is_(None)
        ).first()
        if not npc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"NPC with slug '{payload.npc_slug}' does not exist."
            )

    valid, reasons = QuestValidationEngine.validate_quest(db, payload.model_dump())
    return {"valid": valid, "reasons": reasons}


@router.get("/templates", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
def get_quest_templates():
    return QuestTemplateEngine.get_templates()


@router.get("/generated", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
def get_generated_quests(
    npc_slug: Optional[str] = None,
    player_id: Optional[str] = None,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    header_player_id: str = Depends(get_player_id)
):
    pid = player_id or header_player_id
    # Try cache first if npc_slug and pid are both provided
    if npc_slug and pid:
        cached, hit = DynamicQuestGenerator.get_cached_quest(npc_slug, pid, game_project_id=game_project_id)
        if hit:
            return [cached]

    # Query DB
    query = db.query(GeneratedQuest).filter(GeneratedQuest.game_project_id == game_project_id)
    if npc_slug:
        query = query.filter(GeneratedQuest.npc_slug == npc_slug)
    quests = query.order_by(desc(GeneratedQuest.created_at)).all()

    return [
        {
            "id": str(q.id),
            "npc_slug": q.npc_slug,
            "title": q.title,
            "objectives": q.objectives,
            "rewards": q.rewards,
            "difficulty": q.difficulty,
            "created_at": q.created_at.isoformat() if q.created_at else None
        }
        for q in quests
    ]
