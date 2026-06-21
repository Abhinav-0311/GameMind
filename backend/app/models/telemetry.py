import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Numeric, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base

class LLMTelemetryLog(Base):
    __tablename__ = "llm_telemetry_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String(50), nullable=False, server_default="dialogue", default="dialogue")  # "dialogue", "summarization"
    npc_slug = Column(String(100), nullable=False)
    model_used = Column(String(100), nullable=False)
    llm_provider = Column(String(50), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    input_tokens = Column(Integer, nullable=False, server_default="0", default=0)
    output_tokens = Column(Integer, nullable=False, server_default="0", default=0)
    estimated_cost_usd = Column(Numeric(12, 6), nullable=False, server_default="0.0", default=0.0)
    safety_blocked = Column(Boolean, nullable=False, server_default="false", default=False)
    safety_ratings = Column(JSONB, nullable=True)
    error = Column(String(255), nullable=True)  # Short error classification
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_llm_telemetry_logs_created_at", "created_at"),
        Index("ix_llm_telemetry_logs_npc_slug", "npc_slug"),
        Index("ix_llm_telemetry_logs_action_type", "action_type"),
        Index("ix_llm_telemetry_logs_conversation_id", "conversation_id"),
    )
