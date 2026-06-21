import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Text, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base, ProjectScopedMixin

class NPCRelationship(Base, ProjectScopedMixin):
    __tablename__ = "npc_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(String(100), nullable=False, server_default="default_player", default="default_player")
    npc_slug = Column(String(100), nullable=False)
    trust = Column(Integer, nullable=False, server_default="50", default=50)
    respect = Column(Integer, nullable=False, server_default="50", default=50)
    friendship = Column(Integer, nullable=False, server_default="50", default=50)
    fear = Column(Integer, nullable=False, server_default="0", default=0)
    last_reason = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["game_project_id", "npc_slug"],
            ["npc_profiles.game_project_id", "npc_profiles.slug"],
            ondelete="CASCADE"
        ),
        UniqueConstraint("game_project_id", "player_id", "npc_slug", name="uq_player_npc"),
    )

