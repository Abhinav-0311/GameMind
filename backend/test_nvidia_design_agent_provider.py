import json

import httpx
import pytest

from app.config import Settings
from app.design_agent.nvidia_provider import (
    NvidiaAuthenticationError,
    NvidiaDesignAgentProvider,
    NvidiaNodeConfig,
    NvidiaProviderError,
    NvidiaStructuredOutputError,
    ResilientDesignAgentProvider,
)
from app.design_agent.provider import MockDesignAgentProvider
from app.design_agent.provider_factory import build_design_agent_provider


def _completion(
    content: str,
    *,
    input_tokens: int = 12,
    output_tokens: int = 5,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
            },
        },
    )


def _provider(handler, **overrides) -> NvidiaDesignAgentProvider:
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://integrate.api.nvidia.com/v1",
    )
    node_configs = {
        "plan": NvidiaNodeConfig("test-plan-model", temperature=0.0, max_tokens=400),
        "generate": NvidiaNodeConfig("test-generate-model", temperature=0.1, max_tokens=2000),
        "critique": NvidiaNodeConfig("test-critic-model", temperature=0.0, max_tokens=800),
        "revise": NvidiaNodeConfig("test-revision-model", temperature=0.1, max_tokens=2000),
    }
    return NvidiaDesignAgentProvider(
        api_key="test-secret-key",
        base_url="https://integrate.api.nvidia.com/v1",
        node_configs=node_configs,
        timeout_seconds=1.0,
        max_retries=overrides.pop("max_retries", 2),
        retry_backoff_seconds=0,
        repair_enabled=overrides.pop("repair_enabled", True),
        client=client,
        sleep=lambda _seconds: None,
        **overrides,
    )


def test_nvidia_provider_returns_validated_plan_and_usage():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _completion(
            json.dumps(
                {
                    "objective": "Build a cited game blueprint.",
                    "retrieval_query": "game blueprint levels NPC quests",
                    "required_sections": ["summary"],
                }
            )
        )

    result = _provider(handler).plan(
        "Build a cited game blueprint.",
        ["7f349363-5324-4ec1-8511-0b57b5136e53"],
    )

    assert result.provider_name == "nvidia"
    assert result.model_name == "test-plan-model"
    assert result.content["retrieval_query"] == "game blueprint levels NPC quests"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 5
    assert result.metadata["request_attempts"] == 1
    assert result.metadata["cost_status"] == "unavailable"
    assert requests[0].headers["authorization"] == "Bearer test-secret-key"
    assert "test-secret-key" not in repr(result)


def test_nvidia_provider_tolerates_unavailable_usage_counters():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "objective": "Build a cited game blueprint.",
                                    "retrieval_query": "security missions",
                                    "required_sections": ["summary"],
                                }
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": "unknown",
                    "completion_tokens": None,
                },
            },
        )

    result = _provider(handler).plan("Build a cited game blueprint.", ["document"])

    assert result.usage.input_tokens == 0
    assert result.usage.output_tokens == 0
    assert result.metadata["cost_status"] == "unavailable"


def test_nvidia_provider_retries_rate_limit_then_succeeds():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return _completion(
            json.dumps(
                {
                    "objective": "Build a cited game blueprint.",
                    "retrieval_query": "security missions",
                    "required_sections": ["summary"],
                }
            )
        )

    result = _provider(handler).plan("Build a cited game blueprint.", ["document"])

    assert calls == 2
    assert result.metadata["request_attempts"] == 2
    assert result.metadata["retry_count"] == 1


def test_nvidia_provider_does_not_retry_authentication_failure():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    with pytest.raises(NvidiaAuthenticationError) as captured:
        _provider(handler).plan("Build a cited game blueprint.", ["document"])

    assert calls == 1
    assert captured.value.code == "authentication_failed"
    assert "test-secret-key" not in str(captured.value)
    assert "invalid key" not in str(captured.value)


def test_nvidia_provider_retries_timeout_only_within_budget():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("simulated timeout", request=request)

    with pytest.raises(NvidiaProviderError) as captured:
        _provider(handler, max_retries=1).plan(
            "Build a cited game blueprint.",
            ["document"],
        )

    assert calls == 2
    assert captured.value.code == "provider_timeout"
    assert captured.value.attempts == 2


def test_nvidia_provider_repairs_malformed_json_once():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _completion("not valid json", input_tokens=10, output_tokens=2)
        return _completion(
            json.dumps(
                {
                    "objective": "Build a cited game blueprint.",
                    "retrieval_query": "repaired retrieval query",
                    "required_sections": ["summary"],
                }
            ),
            input_tokens=8,
            output_tokens=4,
        )

    result = _provider(handler).plan("Build a cited game blueprint.", ["document"])

    assert calls == 2
    assert result.content["retrieval_query"] == "repaired retrieval query"
    assert result.metadata["repaired"] is True
    assert result.metadata["repair_attempts"] == 1
    assert result.metadata["request_attempts"] == 2
    assert result.usage.input_tokens == 18
    assert result.usage.output_tokens == 6


def test_nvidia_provider_repair_budget_is_bounded():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _completion("still not json")

    with pytest.raises(NvidiaStructuredOutputError) as captured:
        _provider(handler).plan("Build a cited game blueprint.", ["document"])

    assert calls == 2
    assert captured.value.code == "structured_output_invalid"


def test_resilient_provider_marks_mock_fallback_as_degraded():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    provider = ResilientDesignAgentProvider(
        primary=_provider(handler, max_retries=0),
        fallback=MockDesignAgentProvider(),
    )

    result = provider.plan("Build a cited game blueprint.", ["document"])

    assert result.provider_name == "mock"
    assert result.metadata["degraded"] is True
    assert result.metadata["fallback_from"] == "nvidia"
    assert result.metadata["failure_code"] == "provider_unavailable"
    assert result.metadata["primary_attempts"] == 1


def test_provider_factory_keeps_secrets_out_of_persistable_configuration():
    configured = Settings(
        _env_file=None,
        DESIGN_AGENT_PROVIDER="nvidia",
        DESIGN_AGENT_FALLBACK_TO_MOCK=True,
        NVIDIA_API_KEY="factory-secret-key",
        NVIDIA_PLAN_MODEL_NAME="planner",
        NVIDIA_GENERATE_MODEL_NAME="generator",
        NVIDIA_CRITIQUE_MODEL_NAME="critic",
        NVIDIA_REVISE_MODEL_NAME="reviser",
    )

    provider = build_design_agent_provider(configured)
    serialized = json.dumps(provider.configuration())

    assert provider.name == "nvidia"
    assert provider.configuration()["fallback_enabled"] is True
    assert provider.configuration()["models"]["plan"]["model"] == "planner"
    assert "factory-secret-key" not in serialized
