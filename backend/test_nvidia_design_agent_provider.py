import json

import pytest

from app.config import Settings
from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, RetrievalPlanOutput
from app.design_agent.llm_provider import (
    CompletionRequest,
    CompletionResult,
    NvidiaProvider,
)
from app.design_agent.nvidia_provider import (
    NvidiaDesignAgentProvider,
    ResilientDesignAgentProvider,
)
from app.design_agent.provider import MockDesignAgentProvider
from app.design_agent.provider_factory import build_design_agent_provider


class CapturingProvider:
    name = "capture"

    def __init__(self):
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.requests.append(request)
        content = request.response_model.model_validate(
            {
                "retrieval_query": "CyberRakshak levels NPCs gameplay quests",
            }
        ).model_dump()
        return CompletionResult(
            content=content,
            provider_name="nvidia",
            model_name="configured-test-model",
            metadata={"reasoning_discarded": True},
        )


def test_design_agent_adapter_uses_low_level_completion_boundary():
    low_level = CapturingProvider()
    provider = NvidiaDesignAgentProvider(llm_provider=low_level)

    result = provider.plan(
        "Build a cited game blueprint.",
        ["7f349363-5324-4ec1-8511-0b57b5136e53"],
    )

    assert result.provider_name == "nvidia"
    assert result.model_name == "configured-test-model"
    assert result.content["required_sections"] == list(BLUEPRINT_SECTION_KEYS)
    assert result.content["objective"] == "Build a cited game blueprint."
    assert result.metadata["deterministic_fields"] == [
        "objective",
        "required_sections",
    ]
    assert low_level.requests[0].node_name == "plan"
    assert low_level.requests[0].response_model is RetrievalPlanOutput
    assert low_level.requests[0].messages[0] == {
        "role": "system",
        "content": "detailed thinking off",
    }
    assert "JSON Schema:" in low_level.requests[0].messages[1]["content"]


def test_missing_nvidia_key_falls_back_to_mock_with_visible_degradation():
    primary = NvidiaDesignAgentProvider(
        llm_provider=NvidiaProvider(
            base_url="https://integrate.api.nvidia.com/v1",
            timeout_seconds=25,
            repair_enabled=True,
            key_reader=lambda _name: None,
            sleep=lambda _seconds: None,
        )
    )
    provider = ResilientDesignAgentProvider(
        primary=primary,
        fallback=MockDesignAgentProvider(),
    )

    result = provider.plan("Build a cited game blueprint.", ["document"])

    assert result.provider_name == "mock"
    assert result.metadata["degraded"] is True
    assert result.metadata["fallback_from"] == "nvidia"
    assert result.metadata["failure_code"] == "api_key_missing"
    assert "primary_latency_ms" in result.metadata
    assert result.usage.latency_ms >= result.metadata["primary_latency_ms"]


def test_provider_factory_uses_fixed_models_without_persisting_keys():
    configured = Settings(
        _env_file=None,
        LLM_PROVIDER="nvidia",
        DESIGN_AGENT_PROVIDER=None,
        DESIGN_AGENT_FALLBACK_TO_MOCK=True,
        NVIDIA_NANO_API_KEY="nano-factory-secret",
        NVIDIA_SUPER_API_KEY="super-factory-secret",
    )

    provider = build_design_agent_provider(configured)
    configuration = provider.configuration()
    serialized = json.dumps(configuration)

    assert provider.name == "nvidia"
    assert configuration["fallback_enabled"] is True
    assert (
        configuration["models"]["plan"]["model"]
        == "nvidia/llama-3.1-nemotron-nano-8b-v1"
    )
    assert (
        configuration["models"]["generate_blueprint"]["model"]
        == "nvidia/llama-3.3-nemotron-super-49b-v1.5"
    )
    assert "nano-factory-secret" not in serialized
    assert "super-factory-secret" not in serialized


def test_provider_factory_rejects_unknown_provider():
    configured = Settings(
        _env_file=None,
        LLM_PROVIDER="unsupported",
        DESIGN_AGENT_PROVIDER=None,
    )

    with pytest.raises(ValueError, match="must be either"):
        build_design_agent_provider(configured)
