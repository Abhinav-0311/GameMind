import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Float, Boolean, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base, ProjectScopedMixin

class NPCMemory(Base, ProjectScopedMixin):
    __tablename__ = "npc_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npc_id = Column(UUID(as_uuid=True), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    memory_text = Column(Text, nullable=False)
    memory_type = Column(String(50), nullable=False, server_default="episodic", default="episodic")  # "episodic", "summary"
    importance_score = Column(Float, nullable=False, server_default="1.0", default=1.0)
    chroma_indexed = Column(Boolean, nullable=False, server_default="false", default=False)
    archived = Column(Boolean, nullable=False, server_default="false", default=False)
    metadata_json = Column(JSONB, name="metadata", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["game_project_id", "npc_id"],
            ["npc_profiles.game_project_id", "npc_profiles.id"],
            ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["game_project_id", "conversation_id"],
            ["conversations.game_project_id", "conversations.id"],
            ondelete="SET NULL"
        ),
    )

