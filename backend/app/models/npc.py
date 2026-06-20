import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base

class NPCProfile(Base):
    __tablename__ = "npc_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    title = Column(String(100), nullable=True)
    personality_summary = Column(Text, nullable=False)
    dialogue_style = Column(Text, nullable=True)
    voice_profile = Column(String(100), nullable=True)
    faction_alignment = Column(String(100), nullable=True)
    animation_hints = Column(JSONB, nullable=True)
    memory_settings = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, name="metadata", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
