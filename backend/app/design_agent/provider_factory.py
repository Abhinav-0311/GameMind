from app.config import Settings, settings
from app.design_agent.nvidia_provider import (
    NvidiaDesignAgentProvider,
    NvidiaNodeConfig,
    ResilientDesignAgentProvider,
)
from app.design_agent.provider import DesignAgentProvider, MockDesignAgentProvider


def build_design_agent_provider(
    app_settings: Settings = settings,
) -> DesignAgentProvider:
    """Build the configured provider without weakening the local default."""

    provider_name = app_settings.DESIGN_AGENT_PROVIDER.strip().lower()
    if provider_name == "mock":
        return MockDesignAgentProvider()
    if provider_name != "nvidia":
        raise ValueError(
            "DESIGN_AGENT_PROVIDER must be either 'mock' or 'nvidia'."
        )

    default_model = app_settings.NVIDIA_MODEL_NAME
    primary = NvidiaDesignAgentProvider(
        api_key=app_settings.NVIDIA_API_KEY,
        base_url=app_settings.NVIDIA_BASE_URL,
        node_configs={
            "plan": NvidiaNodeConfig(
                app_settings.NVIDIA_PLAN_MODEL_NAME or default_model,
                temperature=0.0,
                max_tokens=app_settings.NVIDIA_PLAN_MAX_TOKENS,
            ),
            "generate": NvidiaNodeConfig(
                app_settings.NVIDIA_GENERATE_MODEL_NAME or default_model,
                temperature=0.2,
                max_tokens=app_settings.NVIDIA_GENERATE_MAX_TOKENS,
            ),
            "critique": NvidiaNodeConfig(
                app_settings.NVIDIA_CRITIQUE_MODEL_NAME or default_model,
                temperature=0.0,
                max_tokens=app_settings.NVIDIA_CRITIQUE_MAX_TOKENS,
            ),
            "revise": NvidiaNodeConfig(
                app_settings.NVIDIA_REVISE_MODEL_NAME or default_model,
                temperature=0.1,
                max_tokens=app_settings.NVIDIA_REVISE_MAX_TOKENS,
            ),
        },
        timeout_seconds=app_settings.NVIDIA_TIMEOUT_SECONDS,
        max_retries=app_settings.NVIDIA_MAX_RETRIES,
        retry_backoff_seconds=app_settings.NVIDIA_RETRY_BACKOFF_SECONDS,
        repair_enabled=app_settings.NVIDIA_REPAIR_ENABLED,
        json_mode_enabled=app_settings.NVIDIA_JSON_MODE_ENABLED,
    )
    if not app_settings.DESIGN_AGENT_FALLBACK_TO_MOCK:
        return primary
    return ResilientDesignAgentProvider(
        primary=primary,
        fallback=MockDesignAgentProvider(),
    )
