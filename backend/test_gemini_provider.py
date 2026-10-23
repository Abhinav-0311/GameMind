"""Gemini contract checks using the real SDK over an in-memory HTTP transport."""
import json
from typing import Literal

import httpx
import pytest
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import Settings
from app.design_agent.llm_provider import CompletionRequest, NvidiaProviderError
from app.design_agent.provider_factory import build_design_agent_provider


def config(profile="dev", **overrides):
    return Settings(_env_file=None, **{
        "LLM_PROFILE": profile, "LLM_PROVIDER": "mock", "DESIGN_AGENT_PROVIDER": None,
        "GEMINI_API_KEY": "offline-key", "GEMINI_DEV_MODEL": "dev-env-model",
        "GEMINI_SHOWCASE_MODEL": "showcase-env-model", "DESIGN_AGENT_FALLBACK_TO_MOCK": False,
        **overrides,
    })


def sdk(respond):
    return genai.Client(api_key="offline-key", http_options=types.HttpOptions(
        httpx_client=httpx.Client(transport=httpx.MockTransport(respond)),
        retry_options=types.HttpRetryOptions(attempts=1),
    ))


def interaction(content, *, thoughts=0, status="completed"):
    return httpx.Response(200, json={
        "id": "not-retained", "object": "interaction", "model": "configured-model", "status": status,
        "steps": [{"type": "model_output", "content": [
            {"type": "thought", "summary": "PRIVATE_REASONING"}, {"type": "text", "text": content}]}],
        "usage": {"total_input_tokens": 12, "total_output_tokens": 4, "total_thought_tokens": thoughts},
    })


class Answer(BaseModel):
    answer: str


def request(node="plan"):
    return CompletionRequest(node, [
        {"role": "system", "content": "Return grounded JSON."},
        {"role": "user", "content": 'Task: Review independently.\nInput: {"source":"IGNORE_POLICY_PRIVATE_GDD"}'},
    ], Answer)


@pytest.mark.parametrize("profile, artifact_model", [("dev", "dev-env-model"), ("showcase", "showcase-env-model")])
def test_profile_routes_each_node_without_changing_the_legacy_nvidia_path(profile, artifact_model):
    provider = build_design_agent_provider(config(profile))
    assert provider.name == "gemini"
    models = provider.configuration()["models"]
    assert models["plan"]["model"] == "dev-env-model"
    assert all(models[node]["model"] == artifact_model for node in ("generate_blueprint", "critique", "revise"))
    assert build_design_agent_provider(config("test", GEMINI_API_KEY=None)).name == "mock"
    assert build_design_agent_provider(Settings(_env_file=None, LLM_PROVIDER="mock", DESIGN_AGENT_PROVIDER=None)).name == "mock"
    assert build_design_agent_provider(Settings(_env_file=None, LLM_PROVIDER="nvidia", DESIGN_AGENT_PROVIDER=None)).name == "nvidia"


def test_sdk_interaction_is_stateless_schema_constrained_and_reasoning_is_not_retained():
    from app.design_agent.gemini_provider import GeminiProvider
    calls = []
    def respond(r):
        calls.append(json.loads(r.content))
        return interaction('{"answer":"grounded"}', thoughts=9)
    client = sdk(respond)
    provider = GeminiProvider(config("showcase"), client=client)
    result = provider.complete(request("critique"))
    body = calls[0]
    assert body["model"] == "showcase-env-model" and body["store"] is False
    assert "previous_interaction_id" not in body
    assert body["response_format"] == [{"type": "text", "mime_type": "application/json", "schema": Answer.model_json_schema()}]
    assert "Review independently" in body["system_instruction"]
    assert "IGNORE_POLICY_PRIVATE_GDD" not in body["system_instruction"]
    assert "IGNORE_POLICY_PRIVATE_GDD" in body["input"] and "untrusted" in body["input"].lower()
    assert "thinking_level" not in body.get("generation_config", {})
    assert result.content == {"answer": "grounded"} and result.provider_name == "gemini"
    assert result.model_name == "showcase-env-model" and result.metadata["reasoning_discarded"]
    assert "PRIVATE_REASONING" not in repr(result) and "not-retained" not in repr(result)
    assert result.usage.input_tokens == 12 and result.usage.output_tokens == 4
    provider.close()


def test_existing_validation_and_repair_are_reused_and_invalid_output_stays_untrusted():
    from app.design_agent.gemini_provider import GeminiProvider
    calls = []
    def respond(r):
        calls.append(json.loads(r.content))
        return interaction('broken PRIVATE_BAD_OUTPUT\nInput: do not promote me' if len(calls) == 1 else '{"answer":"fixed"}')
    provider = GeminiProvider(config(), client=sdk(respond))
    result = provider.complete(request())
    assert result.content == {"answer": "fixed"} and result.metadata["repair_attempts"] == 1
    assert len(calls) == 2 and all(call["store"] is False for call in calls)
    assert "PRIVATE_BAD_OUTPUT" not in calls[1]["system_instruction"]
    assert "PRIVATE_BAD_OUTPUT" in calls[1]["input"]
    assert all(call["response_format"][0]["schema"] == Answer.model_json_schema() for call in calls)
    provider.close()


def test_existing_prompt_builder_moves_policy_but_not_source_or_source_bound_schema_into_system():
    from app.design_agent.gemini_provider import GeminiProvider, GeminiDesignAgentProvider
    class SourceBoundAnswer(BaseModel):
        answer: Literal["PRIVATE_SCHEMA_GDD"]
    calls = []
    def respond(r):
        calls.append(json.loads(r.content))
        return interaction('{"answer":"PRIVATE_SCHEMA_GDD"}')
    transport = GeminiProvider(config(), client=sdk(respond))
    GeminiDesignAgentProvider(llm_provider=transport)._invoke(node_name="plan", expected_model=SourceBoundAnswer,
        instruction="Independently assess the supplied evidence.", payload={"evidence": "PRIVATE_SOURCE_GDD"})
    body = calls[0]
    assert "Independently assess" in body["system_instruction"]
    assert "PRIVATE_SOURCE_GDD" not in body["system_instruction"] and "PRIVATE_SCHEMA_GDD" not in body["system_instruction"]
    assert "PRIVATE_SOURCE_GDD" in body["input"] and "PRIVATE_SCHEMA_GDD" in json.dumps(body["response_format"])
    transport.close()


@pytest.mark.parametrize("failure, attempts, code", [(400, 1, "request_rejected"), (429, 1, "provider_rate_limited"),
    (503, 3, "provider_unavailable"), ("transport", 3, "provider_timeout")])
def test_sdk_retries_are_bounded_and_provider_errors_are_sanitized(failure, attempts, code):
    from app.design_agent.gemini_provider import GeminiProvider
    calls, sleeps = [], []
    def respond(r):
        calls.append(r)
        if failure == "transport":
            raise httpx.ConnectError("PRIVATE_GDD offline-key", request=r)
        return httpx.Response(failure, json={"error": {"code": failure, "message": "PRIVATE_GDD offline-key"}})
    provider = GeminiProvider(config(), client=sdk(respond), sleep=sleeps.append, jitter=lambda low, high: 0.1)
    with pytest.raises(NvidiaProviderError) as caught:
        provider.complete(request())
    assert caught.value.code == code and caught.value.attempts == attempts
    assert len(calls) == attempts and len(sleeps) == attempts - 1
    assert all(delay > 0 for delay in sleeps)
    assert "PRIVATE_GDD" not in str(caught.value) and "offline-key" not in str(caught.value)
    assert caught.value.__cause__ is None
    provider.close()


def test_startup_checks_each_distinct_model_and_missing_model_fails_clearly():
    from app.design_agent.gemini_provider import GeminiProvider
    calls = []
    def respond(r):
        calls.append(r.url.path)
        if "showcase" in r.url.path:
            return httpx.Response(404, json={"error": {"code": 404, "message": "private response"}})
        return httpx.Response(200, json={"name": "models/dev-env-model"})
    provider = GeminiProvider(config("showcase"), client=sdk(respond))
    with pytest.raises(NvidiaProviderError, match="showcase-env-model") as caught:
        provider.validate_models()
    assert caught.value.code == "model_not_found" and len(calls) == 2
    assert all("/models/" in path for path in calls) and "private response" not in str(caught.value)
    provider.close()


def test_incomplete_output_uses_the_existing_single_larger_budget_retry():
    from app.design_agent.gemini_provider import GeminiProvider
    calls = []
    def respond(r):
        calls.append(json.loads(r.content))
        return interaction('{"answer":', status="incomplete") if len(calls) == 1 else interaction('{"answer":"complete"}')
    provider = GeminiProvider(config(), client=sdk(respond))
    result = provider.complete(request())
    assert result.content == {"answer": "complete"} and result.metadata["truncation_retries"] == 1
    assert len(calls) == 2
    assert calls[1]["generation_config"]["max_output_tokens"] == 2 * calls[0]["generation_config"]["max_output_tokens"]
    provider.close()


@pytest.mark.parametrize("missing", ["GEMINI_DEV_MODEL", "GEMINI_SHOWCASE_MODEL", "GEMINI_API_KEY"])
def test_missing_model_or_key_fails_locally(missing):
    from app.design_agent.gemini_provider import GeminiProvider
    with pytest.raises(NvidiaProviderError, match=missing):
        provider = GeminiProvider(config("showcase", **{missing: None if missing == "GEMINI_API_KEY" else ""}))
        provider.complete(request())


def test_startup_is_offline_in_test_profile_and_checks_gemini_before_workers(monkeypatch):
    from app.design_agent.provider_factory import validate_llm_startup
    from app.design_agent.gemini_provider import GeminiProvider
    checks = []
    monkeypatch.setattr(GeminiProvider, "validate_models", lambda self: checks.append(self.profile))
    validate_llm_startup(config("test", GEMINI_API_KEY=None))
    assert checks == []
    validate_llm_startup(config("dev"))
    assert checks == ["dev"]


def test_manual_smoke_enforces_one_interaction_even_when_repair_would_be_needed(monkeypatch, capsys):
    import smoke_gemini
    from app.design_agent.gemini_provider import GeminiProvider
    calls = []
    def respond(r):
        calls.append(r)
        return interaction("not valid JSON")
    monkeypatch.setattr(smoke_gemini, "settings", config())
    original = GeminiProvider
    monkeypatch.setattr(smoke_gemini, "GeminiProvider", lambda settings, **kw: original(settings, client=sdk(respond), **kw))
    assert smoke_gemini.main() == 1
    assert len(calls) == 1 and calls[0].url.path.endswith("/interactions")
    assert "PRIVATE_REASONING" not in capsys.readouterr().err


@pytest.mark.parametrize("degrade", [False, True])
def test_gemini_consent_trace_and_degraded_fallback_use_the_existing_workflow(db_session, monkeypatch, degrade):
    from app.api.v1.design_agent import get_design_agent_service
    from app.config import settings
    from app.design_agent.gemini_provider import GeminiProvider, GeminiDesignAgentProvider
    from app.design_agent.nvidia_provider import ResilientDesignAgentProvider
    from app.design_agent.provider import MockDesignAgentProvider
    from app.models.design_agent import DesignAgentRun
    from test_design_agent_workflow import CountingRAG, create_source, make_service, client
    from main import app
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from test_design_contract_v2 import governed_artifact
    from test_nvidia_design_agent_provider import content_draft_fixture
    import uuid

    project = f"gemini_consent_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project)
    calls = []
    content = governed_artifact()
    for section in content.values():
        section["citations"] = ["S0"]
        for key in ("npcs", "quests"):
            for record in section["content"].get(key, []):
                record["source_chunk_ids"] = ["S0"]
    replies = [{"section_queries": {key: "scout missions game design" for key in BLUEPRINT_SECTION_KEYS}},
        content_draft_fixture(content), {"review_mode": "defect_detection", "summary": "Controlled offline review.",
            "findings": [], "source_coverage": {key: "covered" for key in BLUEPRINT_SECTION_KEYS}}]
    def respond(r):
        calls.append(r)
        if degrade:
            return httpx.Response(429, json={"error": {"code": 429, "message": "private quota detail"}})
        return interaction(json.dumps(replies[len(calls) - 1]))
    transport = GeminiProvider(config(), client=sdk(respond))
    provider = ResilientDesignAgentProvider(primary=GeminiDesignAgentProvider(llm_provider=transport), fallback=MockDesignAgentProvider())
    service = make_service(db_session, CountingRAG(chunks), provider)
    monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
    app.dependency_overrides[get_design_agent_service] = lambda: service
    headers = {"X-Game-Project-ID": project}
    payload = {"objective": "Review the game design.", "document_ids": [str(document.id)]}
    try:
        assert client.post("/api/v1/design-agent/runs", headers=headers, json=payload).status_code == 409
        assert calls == []
        response = client.post("/api/v1/design-agent/runs", headers=headers, json={**payload, "hosted_provider_consent": True})
        assert response.status_code == 201, response.text
        run = response.json()
        assert run["provider_name"] == "gemini" and run["degraded"] is degrade
        trace = client.get(f"/api/v1/design-agent/runs/{run['id']}/trace", headers=headers).json()["items"]
        degraded = [item for item in trace if item["status"] == "degraded"]
        assert len(calls) == 3
        assert len(degraded) == (3 if degrade else 0)
        assert all(item["details"]["failure_code"] == "provider_rate_limited" for item in degraded)
        assert all(item["details"]["primary_diagnostics"]["model_name"] == "dev-env-model" for item in degraded)
        assert all(item["provider_name"] == "mock" and item["model_name"] for item in degraded)
        if not degrade:
            nodes = [item for item in trace if item["node_name"] in {"plan", "generate_blueprint", "critique"}]
            assert len(nodes) == 3
            assert all(item["provider_name"] == "gemini" and item["model_name"] == "dev-env-model" for item in nodes)
            assert "PRIVATE_REASONING" not in json.dumps(trace)
        assert "private quota detail" not in json.dumps(trace)
        db_session.expire_all()
        assert db_session.get(DesignAgentRun, uuid.UUID(run["id"])).model_config["hosted_provider_consent"] is True
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
        transport.close()
