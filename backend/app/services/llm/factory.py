import logging
from app.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.gemini import GeminiProvider
from app.services.llm.mock import MockLLMProvider

logger = logging.getLogger(__name__)

def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "gemini":
        # Check if the API key is not configured, empty, or uses the placeholder template string
        is_key_missing = (
            not settings.GEMINI_API_KEY or 
            settings.GEMINI_API_KEY.strip() in ("", "your_gemini_api_key_here")
        )
        if is_key_missing:
            logger.warning(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is missing or invalid. Falling back to MockLLMProvider."
            )
            return MockLLMProvider()
        return GeminiProvider(api_key=settings.GEMINI_API_KEY)
    
    # Defaults to Mock provider (e.g. for LLM_PROVIDER=mock or fallback)
    return MockLLMProvider()
