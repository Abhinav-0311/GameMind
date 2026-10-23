import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

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
    assert default_plan.disable_thinking is True

    monkeypatch.setenv("NVIDIA_PLAN_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
    monkeypatch.setenv("NVIDIA_PLAN_API_KEY_ENV", "NVIDIA_SUPER_API_KEY")
    monkeypatch.setenv("NVIDIA_PLAN_MAX_TOKENS", "1024")
    overridden_plan = _plan_model_config()
    assert overridden_plan.model == "nvidia/llama-3.3-nemotron-super-49b-v1.5"
    assert overridden_plan.api_key_env == "NVIDIA_SUPER_API_KEY"
    assert overridden_plan.max_tokens == 1024
    assert overridden_plan.disable_thinking is True

    monkeypatch.delenv("NVIDIA_ARTIFACT_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_ARTIFACT_API_KEY_ENV", raising=False)
    default_artifact = _artifact_model_config(max_tokens=8000)
    assert default_artifact.model == "nvidia/nemotron-3-super-120b-a12b"
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


def test_planner_model_boundary_owns_search_queries_not_workflow_scope():
    section_queries = {section: f"evidence for {section}" for section in BLUEPRINT_SECTION_KEYS}
    output = RetrievalPlanOutput.model_validate(
        {
            "retrieval_query": "all game levels NPC memories and quest systems",
            "section_queries": section_queries,
            "objective": "The model must not own this field.",
            "required_sections": ["summary"],
        }
    )

    assert output.model_dump() == {
        "retrieval_query": "all game levels NPC memories and quest systems",
        "section_queries": section_queries,
    }
    assert RetrievalPlanOutput(retrieval_query="legacy query").section_queries == {}
    for invalid_queries in (
        {"summary": "overview"},
        {**section_queries, "outside_workflow": "unrelated"},
        {**section_queries, "summary": "   "},
        {**section_queries, "summary": "x" * 501},
    ):
        with pytest.raises(ValidationError):
            RetrievalPlanOutput(retrieval_query="game evidence", section_queries=invalid_queries)


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


@pytest.mark.parametrize("valid_retry", [True, False])
def test_malformed_independent_review_gets_one_fresh_review_not_a_repair(valid_retry):
    from app.design_agent.contracts import GovernedCritiqueOutput
    from app.design_agent.llm_provider import NvidiaStructuredOutputError

    finding = {"severity": "high", "section": "summary", "issue": "Source premise is absent.",
               "recommendation": "Restore the cited premise.", "reference": {
                   "artifact_path": "/summary/content/description", "artifact_value": None,
                   "replacement": "A tactical RPG.", "evidence_chunk_id": "source",
                   "evidence_quote": "A tactical RPG."}}
    review = {"verdict": "needs_revision", "summary": "The premise is missing.",
              "source_coverage": {section: "covered" for section in BLUEPRINT_SECTION_KEYS}, "findings": [finding]}
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        return _completion(json.dumps(review) if valid_retry and len(calls) == 2 else '{"findings":[}')
    request = CompletionRequest(node_name="critique", messages=[{"role": "user", "content": "Review frozen draft and evidence."}],
                                response_model=GovernedCritiqueOutput)
    provider = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=True,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond)))
    if valid_retry:
        result = provider.complete(request)
        assert result.content["findings"] == [finding] and result.content["verdict"] == "needs_revision"
        assert result.metadata["request_attempts"] == 2 and result.metadata["retry_count"] == 1
        assert result.metadata["independent_review_retries"] == 1
        assert result.metadata["repair_attempts"] == 0 and not result.metadata["repaired"]
        assert result.usage.input_tokens == 20 and result.usage.output_tokens == 10
    else:
        with pytest.raises(NvidiaStructuredOutputError) as caught:
            provider.complete(request)
        assert caught.value.attempts == 2
    assert len(calls) == 2 and calls[1] == calls[0]


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
    assert captured[0]["payload"]["chat_template_kwargs"] == {"enable_thinking": False}
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
    assert "guided_json" not in captured[0] and "nvext" not in captured[0]
    assert captured[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "gamemind_response", "strict": True, "schema": ResearchPlan.model_json_schema()},
    }


@pytest.mark.parametrize("status", [400, 422])
def test_structured_request_rejection_does_not_silently_retry_without_schema(status):
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(status, json={"error": "private provider details"})
    provider = NvidiaProvider(base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(respond)), key_reader=lambda _: "test-secret")
    request = CompletionRequest(node_name="revise", messages=[], response_model=ResearchPlan, guided_json=True)
    with pytest.raises(NvidiaProviderError) as caught:
        provider.complete(request)
    assert len(calls) == 1 and caught.value.attempts == 1 and caught.value.code == "request_rejected"
    assert calls[0]["response_format"]["json_schema"]["strict"] is True
    assert "private provider details" not in str(caught.value)
    assert caught.value.diagnostics["http_status"] == status


@pytest.mark.parametrize("status,retry_after,attempts,delays,success", [
    (503, None, 3, [0.5, 1.0], False),
    (429, "1", 2, [1.0], True),
    (503, "2", 2, [2.0], True),
    (503, "0", 2, [0.5], True),
    (503, "60", 1, [], False),
    (503, "future-date", 1, [], False),
    (503, "past-date", 2, [0.5], True),
    (429, "private-invalid-header", 2, [0.5], True),
    (429, "NaN", 2, [0.5], True),
    (429, "-1", 2, [0.5], True),
    pytest.param(503, "9" * 5000, 1, [], False, id="oversized-cooldown"),
    (401, "1", 1, [], False),
    (403, None, 1, [], False),
])
def test_http_failure_diagnostics_and_bounded_cooldown(status, retry_after, attempts, delays, success):
    if retry_after in {"future-date", "past-date"}:
        offset = 60 if retry_after == "future-date" else -60
        retry_after = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=offset), usegmt=True)
    calls, slept = [], []

    def respond(request):
        calls.append(request)
        if success and len(calls) == 2:
            return _completion(_valid_plan())
        return httpx.Response(status, json={"error": "private response test-secret"},
            headers={"Retry-After": retry_after} if retry_after is not None else {})

    provider = NvidiaProvider(base_url="https://example.invalid/v1", timeout_seconds=1,
        repair_enabled=False, client=httpx.Client(transport=httpx.MockTransport(respond)),
        key_reader=lambda _: "test-secret", sleep=slept.append)
    if success:
        assert provider.complete(_request("plan")).metadata["request_attempts"] == attempts
    else:
        with pytest.raises(NvidiaProviderError) as caught:
            provider.complete(_request("plan"))
        error = caught.value
        assert error.attempts == attempts and error.diagnostics["http_status"] == status
        assert error.code == ("authentication_failed" if status in {401, 403} else "provider_unavailable")
        rendered = str(error) + json.dumps(error.diagnostics)
        assert "test-secret" not in rendered and "private" not in rendered
        if status == 503 and attempts == 1:
            assert error.diagnostics["retry_skipped"] == "retry_after_exceeds_backoff_budget"
    assert len(calls) == attempts and slept == delays


def test_nvidia_provider_disables_thinking_for_artifact_nodes(monkeypatch):
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return _completion(_valid_plan())

    monkeypatch.setenv("NVIDIA_ARTIFACT_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    monkeypatch.setenv("NVIDIA_ARTIFACT_DISABLE_THINKING", "true")
    monkeypatch.setitem(
        NODE_MODEL_CONFIG,
        "generate_blueprint",
        _artifact_model_config(max_tokens=128),
    )
    provider = NvidiaProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout_seconds=25,
        repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda _name: "test-secret",
        sleep=lambda _seconds: None,
    )

    provider.complete(_request("generate_blueprint"))

    assert captured[0]["chat_template_kwargs"] == {"enable_thinking": False}


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


def test_nvidia_provider_keeps_planner_thinking_off_through_truncation_and_repair():
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
        if len(payloads) == 2:
            return _completion("not valid JSON")
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

    assert len(payloads) == 3
    assert payloads[1]["max_tokens"] > payloads[0]["max_tokens"]
    assert all(payload["chat_template_kwargs"] == {"enable_thinking": False} for payload in payloads)
    assert result.metadata["truncation_retries"] == 1
    assert result.metadata["repair_attempts"] == 1
    assert result.metadata["request_attempts"] == 3


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
