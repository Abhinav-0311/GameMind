"""Provider-wide reservation ledger; contains no prompts, credentials or reasoning."""
from sqlalchemy import Boolean, CheckConstraint, Column, Date, Integer, String, text
from app.database import Base


class GeminiDailyUsage(Base):
    __tablename__ = "gemini_daily_usage"
    __table_args__ = (CheckConstraint("requests >= 0", name="ck_gemini_usage_nonnegative"),)

    model_id = Column(String(255), primary_key=True)
    pacific_day = Column(Date, primary_key=True)
    requests = Column(Integer, nullable=False, server_default="0")
    exhausted = Column(Boolean, nullable=False, server_default=text("false"))
