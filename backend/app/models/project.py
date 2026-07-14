from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from app.database import Base


class GameProject(Base):
    """A named workspace that owns the existing project-scoped records."""

    __tablename__ = "game_projects"

    id = Column(String(100), primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
