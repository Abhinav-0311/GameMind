from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base

class WorldStateFlag(Base):
    __tablename__ = "world_state_flags"

    flag_key = Column(String(100), primary_key=True)
    flag_value = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
