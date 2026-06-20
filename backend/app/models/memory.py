import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base

class NPCMemory(Base):
    __tablename__ = "npc_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npc_id = Column(UUID(as_uuid=True), ForeignKey("npc_profiles.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    memory_text = Column(Text, nullable=False)
    memory_type = Column(String(50), nullable=False, default="episodic")  # "episodic", "summary"
    importance_score = Column(Float, nullable=False, default=1.0)
    chroma_indexed = Column(Boolean, nullable=False, default=False)
    archived = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(JSONB, name="metadata", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
