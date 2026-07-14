import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base, ProjectScopedMixin


class DesignDecision(Base, ProjectScopedMixin):
    """A human-owned answer to a source-review gap for one GDD revision."""

    __tablename__ = "design_decisions"
    __table_args__ = (
        UniqueConstraint("game_project_id", "document_id", "category", name="uq_design_decisions_project_document_category"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    title = Column(String(160), nullable=False)
    guidance = Column(Text, nullable=True)
    severity = Column(String(30), nullable=False, server_default="needs_decision")
    decision = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, server_default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
