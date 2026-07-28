from app.config import Settings, settings
from app.design_agent.llm_provider import NvidiaProvider
from app.design_agent.nvidia_provider import (
    NvidiaDesignAgentProvider,
    ResilientDesignAgentProvider,
)
from app.design_agent.provider import DesignAgentProvider, MockDesignAgentProvider


def build_design_agent_provider(
    app_settings: Settings = settings,
) -> DesignAgentProvider:
    """Build the configured provider without weakening the local default."""

    provider_name = (
        app_settings.DESIGN_AGENT_PROVIDER or app_settings.LLM_PROVIDER
    ).strip().lower()
    if provider_name == "mock":
        return MockDesignAgentProvider()
    if provider_name != "nvidia":
        raise ValueError(
            "LLM_PROVIDER/DESIGN_AGENT_PROVIDER must be either 'mock' or 'nvidia'."
        )

    primary = NvidiaDesignAgentProvider(
        llm_provider=NvidiaProvider(
            base_url=app_settings.NVIDIA_BASE_URL,
            timeout_seconds=app_settings.NVIDIA_TIMEOUT_SECONDS,
            repair_enabled=app_settings.NVIDIA_REPAIR_ENABLED,
            retry_backoff_seconds=app_settings.NVIDIA_RETRY_BACKOFF_SECONDS,
            key_reader=lambda name: getattr(app_settings, name, None),
        )
    )
    if not app_settings.DESIGN_AGENT_FALLBACK_TO_MOCK:
        return primary
    return ResilientDesignAgentProvider(
        primary=primary,
        fallback=MockDesignAgentProvider(),
    )
