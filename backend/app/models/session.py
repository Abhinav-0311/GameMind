import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base, ProjectScopedMixin

class Conversation(Base, ProjectScopedMixin):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npc_id = Column(UUID(as_uuid=True), nullable=False)
    npc_slug = Column(String(100), nullable=False)
    title = Column(String(255), nullable=True)
    conversation_summary = Column(Text, nullable=True)
    last_summarized_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", name="fk_conversations_last_summarized_message", ondelete="SET NULL", use_alter=True), nullable=True)
    summary_version = Column(Integer, nullable=False, server_default="0", default=0)
    summary_updated_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, server_default="active", default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["game_project_id", "npc_id"],
            ["npc_profiles.game_project_id", "npc_profiles.id"],
            ondelete="CASCADE"
        ),
        UniqueConstraint("game_project_id", "id", name="uq_conversation_project_id"),
    )


    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at", foreign_keys="[Message.conversation_id]")

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String(50), nullable=False)  # "player" or "npc"
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, name="metadata", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages", foreign_keys="[Message.conversation_id]")
