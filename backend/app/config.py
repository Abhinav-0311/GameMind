from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate the project root (.env directory) relative to this file
current_dir = Path(__file__).resolve().parent  # backend/app
project_root = current_dir.parent.parent       # E:\College\Project\Bot
env_path = project_root / ".env"

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/dbname"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    LLM_PROVIDER: str = "mock"
    LOCAL_MODEL_NAME: str = "local-rule-engine"
    NVIDIA_API_KEY: str | None = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL_NAME: str = "meta/llama-3.1-8b-instruct"

    model_config = SettingsConfigDict(
        env_file=str(env_path),
        extra="ignore"
    )

settings = Settings()
