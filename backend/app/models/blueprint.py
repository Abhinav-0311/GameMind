import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base, ProjectScopedMixin

class GameBlueprint(Base, ProjectScopedMixin):
    __tablename__ = "game_blueprints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    
    # Section structure: {"content": {...}, "citations": [...], "confidence": "...", "warnings": [...]}
    summary = Column(JSONB, nullable=False)
    narrative_direction = Column(JSONB, nullable=False)
    art_style_direction = Column(JSONB, nullable=False)
    npc_archetypes = Column(JSONB, nullable=False)
    npc_memory_design = Column(JSONB, nullable=False)
    level_design_suggestions = Column(JSONB, nullable=False)
    quest_hooks = Column(JSONB, nullable=False)
    unity_runtime_preview = Column(JSONB, nullable=False)

    status = Column(String(50), nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Establish relationship to Document
    document = relationship("Document")
