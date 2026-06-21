from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base, ProjectScopedMixin

class WorldStateFlag(Base, ProjectScopedMixin):
    __tablename__ = "world_state_flags"

    game_project_id = Column(String(100), primary_key=True, server_default="default_project", default="default_project")
    flag_key = Column(String(100), primary_key=True)
    flag_value = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true", default=True)
    priority = Column(Integer, nullable=False, server_default="0", default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
