import json

import httpx
import pytest
from pydantic import ValidationError

from app.design_agent.contracts import (
    BLUEPRINT_SECTION_KEYS,
    ResearchPlan,
    RetrievalPlanOutput,
)
from app.design_agent.llm_provider import (
    CompletionRequest,
    MockProvider,
    NODE_MODEL_CONFIG,
    NvidiaProvider,
    NvidiaProviderError,
    NvidiaTruncatedOutputError,
    _artifact_model_config,
    _plan_model_config,
)


def _request(node_name: str) -> CompletionRequest:
    return CompletionRequest(
        node_name=node_name,
        messages=[
            {"role": "system", "content": "detailed thinking off"},
            {
                "role": "user",
                "content": "Return only a valid GameMind research-plan JSON object.",
            },
        ],
        response_model=ResearchPlan,
    )


def _completion(
    content: str,
    *,
    finish_reason: str = "stop",
    reasoning: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> httpx.Response:
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
        message["reasoning"] = reasoning
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
            },
        },
    )


def _valid_plan(query: str = "all nine CyberRakshak levels") -> str:
    return json.dumps(
        {
            "objective": "Create a cited CyberRakshak blueprint.",
            "retrieval_query": query,
            "required_sections": [
                "summary",
                "narrative_direction",
                "art_style_direction",
                "npc_archetypes",
                "npc_memory_design",
                "level_design_suggestions",
                "gameplay_systems",
                "quest_hooks",
                "unity_runtime_preview",
            ],
        }
    )


def test_node_model_config_uses_nano_by_default_and_allows_explicit_plan_override(monkeypatch):
    monkeypatch.delenv("NVIDIA_PLAN_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_PLAN_API_KEY_ENV", raising=False)
    monkeypatch.delenv("NVIDIA_PLAN_MAX_TOKENS", raising=False)
    default_plan = _plan_model_config()
    assert default_plan.model == "nvidia/llama-3.1-nemotron-nano-8b-v1"
    assert default_plan.api_key_env == "NVIDIA_NANO_API_KEY"
    assert default_plan.max_tokens == 300

    monkeypatch.setenv("NVIDIA_PLAN_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
    monkeypatch.setenv("NVIDIA_PLAN_API_KEY_ENV", "NVIDIA_SUPER_API_KEY")
    monkeypatch.setenv("NVIDIA_PLAN_MAX_TOKENS", "1024")
    overridden_plan = _plan_model_config()
    assert overridden_plan.model == "nvidia/llama-3.3-nemotron-super-49b-v1.5"
    assert overridden_plan.api_key_env == "NVIDIA_SUPER_API_KEY"
    assert overridden_plan.max_tokens == 1024

    monkeypatch.delenv("NVIDIA_ARTIFACT_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_ARTIFACT_API_KEY_ENV", raising=False)
    default_artifact = _artifact_model_config(max_tokens=8000)
    assert default_artifact.model == "nvidia/llama-3.3-nemotron-super-49b-v1.5"
    assert default_artifact.api_key_env == "NVIDIA_SUPER_API_KEY"

    monkeypatch.setenv("NVIDIA_ARTIFACT_MODEL", "meta/llama-3.1-8b-instruct")
    overridden_artifact = _artifact_model_config(max_tokens=2048)
    assert overridden_artifact.model == "meta/llama-3.1-8b-instruct"
    assert overridden_artifact.api_key_env == "NVIDIA_SUPER_API_KEY"


def test_research_plan_rejects_generic_or_incomplete_section_lists():
    with pytest.raises(ValidationError, match="every GameMind blueprint section"):
        ResearchPlan.model_validate(
            {
                "objective": "Create a generic report.",
                "retrieval_query": "market research",
                "required_sections": ["summary"],
            }
        )

    complete = ResearchPlan(
        objective="Create a GameMind blueprint.",
        retrieval_query="CyberRakshak game design",
        required_sections=list(reversed(BLUEPRINT_SECTION_KEYS)),
    )
    assert complete.required_sections == list(BLUEPRINT_SECTION_KEYS)


def test_planner_model_boundary_owns_only_the_retrieval_query():
    output = RetrievalPlanOutput.model_validate(
        {
            "retrieval_query": "all game levels NPC memories and quest systems",
            "objective": "The model must not own this field.",
            "required_sections": ["summary"],
        }
    )

    assert output.model_dump() == {
        "retrieval_query": "all game levels NPC memories and quest systems"
    }


def test_scriptable_mock_returns_sequential_responses_for_same_node():
    provider = MockProvider(
        {
            "plan": [
                json.loads(_valid_plan("first query")),
                json.loads(_valid_plan("second query")),
            ]
        }
    )

    first = provider.complete(_request("plan"))
    second = provider.complete(_request("plan"))

    assert first.content["retrieval_query"] == "first query"
    assert second.content["retrieval_query"] == "second query"
    assert first.metadata["script_index"] == 0
    assert second.metadata["script_index"] == 1


def test_nvidia_provider_uses_node_specific_model_and_key():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "authorization": request.headers["authorization"],
                "payload": json.loads(request.content),
            }
        )
        return _completion(_valid_plan())

    provider = NvidiaProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout_seconds=25,
        repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda name: {
            "NVIDIA_NANO_API_KEY": "nano-secret",
            "NVIDIA_SUPER_API_KEY": "super-secret",
        }.get(name),
        sleep=lambda _seconds: None,
    )

    result = provider.complete(_request("plan"))

    assert result.model_name == NODE_MODEL_CONFIG["plan"].model
    expected_secret = (
        "super-secret"
        if NODE_MODEL_CONFIG["plan"].api_key_env == "NVIDIA_SUPER_API_KEY"
        else "nano-secret"
    )
    assert captured[0]["authorization"] == f"Bearer {expected_secret}"
    assert captured[0]["payload"]["model"] == NODE_MODEL_CONFIG["plan"].model
    assert "response_format" not in captured[0]["payload"]


def test_nvidia_provider_sends_native_json_schema_when_requested():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return _completion(_valid_plan())

    provider = NvidiaProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout_seconds=25,
        repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda _name: "test-secret",
        sleep=lambda _seconds: None,
    )

    result = provider.complete(
        CompletionRequest(
            node_name="plan",
            messages=_request("plan").messages,
            response_model=ResearchPlan,
            guided_json=True,
        )
    )

    assert result.content["objective"]
    assert captured[0]["guided_json"] == ResearchPlan.model_json_schema()


def test_nvidia_provider_discards_reasoning_and_parses_visible_content_only():
    def handler(_request: httpx.Request) -> httpx.Response:
        return _completion(
            _valid_plan(),
            reasoning="private reasoning that must never be persisted",
        )

    provider = NvidiaProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout_seconds=25,
        repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda _name: "secret",
        sleep=lambda _seconds: None,
    )

    result = provider.complete(_request("plan"))

    assert result.content["retrieval_query"] == "all nine CyberRakshak levels"
    assert result.metadata["reasoning_discarded"] is True
    assert "private reasoning" not in repr(result)


def test_nvidia_provider_retries_truncation_with_larger_budget():
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        if len(payloads) == 1:
            return _completion(
                "",
                finish_reason="length",
                reasoning="reasoning consumed the first output budget",
            )
        return _completion(_valid_plan())

    provider = NvidiaProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout_seconds=25,
        repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda _name: "secret",
        sleep=lambda _seconds: None,
    )

    result = provider.complete(_request("plan"))

    assert len(payloads) == 2
    assert payloads[1]["max_tokens"] > payloads[0]["max_tokens"]
    assert result.metadata["truncation_retries"] == 1
    assert result.metadata["request_attempts"] == 2


def test_nvidia_provider_stops_after_one_truncation_retry():
    def handler(_request: httpx.Request) -> httpx.Response:
        return _completion("", finish_reason="length", reasoning="still truncated")

    provider = NvidiaProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout_seconds=25,
        repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda _name: "secret",
        sleep=lambda _seconds: None,
    )

    with pytest.raises(NvidiaTruncatedOutputError):
        provider.complete(_request("plan"))


def test_transport_errors_do_not_chain_sensitive_header_details():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.LocalProtocolError(
            "Illegal header value b'Bearer secret-that-must-not-escape'"
        )

    provider = NvidiaProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout_seconds=25,
        repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda _name: "secret-that-must-not-escape",
        sleep=lambda _seconds: None,
    )

    with pytest.raises(NvidiaProviderError) as captured:
        provider.complete(_request("plan"))

    assert captured.value.code == "provider_timeout"
    assert captured.value.__cause__ is None
    assert "secret-that-must-not-escape" not in str(captured.value)
