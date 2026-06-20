import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base

class Quest(Base):
    __tablename__ = "quests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npc_slug = Column(String(100), ForeignKey("npc_profiles.slug", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=False)
    difficulty = Column(String(50), nullable=False, default="Medium")
    gold_reward = Column(Integer, nullable=False, default=0)
    xp_reward = Column(Integer, nullable=False, default=0)
    item_rewards = Column(JSONB, nullable=True) # List of item names (strings)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class QuestObjective(Base):
    __tablename__ = "quest_objectives"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quest_id = Column(UUID(as_uuid=True), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    objective_index = Column(Integer, nullable=False)
    description = Column(String, nullable=False)
    target_type = Column(String(50), nullable=False) # e.g. "kill", "retrieve", "speak"
    target_id = Column(String(100), nullable=False) # e.g. "void_slime", "wind_valve"
    quantity_required = Column(Integer, nullable=False, default=1)

class QuestProgress(Base):
    __tablename__ = "quest_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(String(100), nullable=False, default="default_player")
    quest_id = Column(UUID(as_uuid=True), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    quest_giver_slug = Column(String(100), ForeignKey("npc_profiles.slug", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="active") # "active", "completed", "failed"
    objectives_state = Column(JSONB, nullable=False) # e.g. {"0": 1, "1": 0} (index -> quantity_current)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

class GeneratedQuest(Base):
    __tablename__ = "generated_quests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npc_slug = Column(String(100), ForeignKey("npc_profiles.slug", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    objectives = Column(JSONB, nullable=False) # List of objective dicts
    rewards = Column(JSONB, nullable=False) # Dict of rewards (gold, xp, items)
    difficulty = Column(String(50), nullable=False, default="Medium")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

