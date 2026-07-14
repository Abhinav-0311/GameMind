import uuid
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base, ProjectScopedMixin

class Document(Base, ProjectScopedMixin):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    content_type = Column(String(50), nullable=False)
    source_kind = Column(String(40), nullable=False, server_default="general", default="general")
    content_hash = Column(String(64), nullable=True)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    revision_number = Column(Integer, nullable=False, server_default="1", default=1)
    file_path = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Establish relationship to chunks
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="joined")
    source_document = relationship("Document", remote_side=[id], foreign_keys=[source_document_id])

    @property
    def chunks_count(self) -> int:
        return len(self.chunks) if self.chunks else 0


Index("ix_documents_project_content_hash", Document.game_project_id, Document.content_hash)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, name="metadata", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Establish back-populates to document
    document = relationship("Document", back_populates="chunks")
