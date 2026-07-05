import logging
from app.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockLLMProvider

logger = logging.getLogger(__name__)

def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER not in {"mock", "local", "local_mock"}:
        logger.warning("Unsupported LLM_PROVIDER=%s. Falling back to local mock provider.", settings.LLM_PROVIDER)
    return MockLLMProvider()


def get_provider_name(provider: LLMProvider) -> str:
    provider_name = getattr(provider, "provider_name", "local_mock")
    if isinstance(provider_name, str) and provider_name.strip():
        return provider_name
    return "local_mock"
