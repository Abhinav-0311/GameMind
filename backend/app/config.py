import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate the project root (.env directory) relative to this file
current_dir = Path(__file__).resolve().parent  # backend/app
project_root = current_dir.parent.parent       # E:\College\Project\Bot
env_path = project_root / ".env"

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    AUTH_REQUIRED: bool = False
    JWT_SECRET: str = "development-only-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    BOOTSTRAP_ADMIN_EMAIL: str | None = None
    AUTH_RATE_LIMIT_ENABLED: bool | None = None
    AUTH_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 900
    REQUIRE_EMAIL_VERIFICATION: bool | None = None
    PUBLIC_APP_URL: str = "http://localhost:3000"
    EMAIL_DELIVERY_MODE: str = "disabled"
    EMAIL_FROM_ADDRESS: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
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
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        """Return a normalized, explicit browser-origin allowlist."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_testing(self) -> bool:
        """Keep test-only infrastructure choices out of normal application settings."""
        return os.getenv("GAMEMIND_TESTING") == "1"

    @property
    def auth_rate_limit_enabled(self) -> bool:
        """Enable local login protection in production unless explicitly overridden."""
        if self.AUTH_RATE_LIMIT_ENABLED is not None:
            return self.AUTH_RATE_LIMIT_ENABLED
        return self.ENVIRONMENT.lower() == "production"

    @property
    def require_email_verification(self) -> bool:
        if self.REQUIRE_EMAIL_VERIFICATION is not None:
            return self.REQUIRE_EMAIL_VERIFICATION
        return self.ENVIRONMENT.lower() == "production"

    model_config = SettingsConfigDict(
        env_file=str(env_path),
        extra="ignore"
    )

settings = Settings()


def validate_production_settings() -> None:
    """Reject known-unsafe public deployment settings before serving traffic."""
    if settings.ENVIRONMENT.lower() != "production":
        return

    problems: list[str] = []
    jwt_secret = settings.JWT_SECRET.strip()
    if jwt_secret == "development-only-change-me" or len(jwt_secret) < 32:
        problems.append("JWT_SECRET must be a unique value of at least 32 characters")
    if not settings.AUTH_REQUIRED:
        problems.append("AUTH_REQUIRED must be true in production")
    if not settings.cors_origins:
        problems.append("CORS_ORIGINS must list the dashboard origin")
    elif any(not origin.startswith("https://") for origin in settings.cors_origins):
        problems.append("CORS_ORIGINS must contain HTTPS origins only in production")
    if settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS < 1 or settings.AUTH_RATE_LIMIT_WINDOW_SECONDS < 1:
        problems.append("auth rate-limit settings must be positive")
    if settings.require_email_verification and (
        settings.EMAIL_DELIVERY_MODE != "smtp"
        or not settings.SMTP_HOST
        or not settings.EMAIL_FROM_ADDRESS
        or "example" in settings.SMTP_HOST.lower()
        or "replace-with" in settings.SMTP_USERNAME.lower()
        or "replace-with" in settings.SMTP_PASSWORD.lower()
    ):
        problems.append("SMTP delivery must be configured when email verification is required")

    if problems:
        raise RuntimeError("Invalid production configuration: " + "; ".join(problems))
