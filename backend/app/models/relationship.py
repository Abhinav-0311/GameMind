import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class NPCRelationship(Base):
    __tablename__ = "npc_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(String(100), nullable=False, default="default_player")
    npc_slug = Column(String(100), ForeignKey("npc_profiles.slug", ondelete="CASCADE"), nullable=False)
    trust = Column(Integer, nullable=False, default=50)
    respect = Column(Integer, nullable=False, default=50)
    friendship = Column(Integer, nullable=False, default=50)
    fear = Column(Integer, nullable=False, default=0)
    last_reason = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("player_id", "npc_slug", name="uq_player_npc"),
    )
