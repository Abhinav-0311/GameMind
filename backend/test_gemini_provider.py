"""Gemini contract checks using the real SDK over an in-memory HTTP transport."""
import json
import copy
from pathlib import Path
from typing import Literal

import httpx
import pytest
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import Settings
from app.design_agent.llm_provider import CompletionRequest, NvidiaProviderError
from app.design_agent.provider_factory import build_design_agent_provider


@pytest.fixture(autouse=True)
def isolate_provider_quota(db_session, monkeypatch):
    from app.design_agent import gemini_budget
    from app.design_agent.gemini_provider import GeminiProvider
    from app.models.gemini_usage import GeminiDailyUsage
    db_session.query(GeminiDailyUsage).delete()
    db_session.commit()
    monkeypatch.setattr(gemini_budget, "process_window", gemini_budget.SlidingWindow())
    monkeypatch.setattr(GeminiProvider, "_verified_models", set())


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
    assert build_design_agent_provider(Settings(_env_file=None, LLM_PROFILE=None, LLM_PROVIDER="mock", DESIGN_AGENT_PROVIDER=None)).name == "mock"
    assert build_design_agent_provider(Settings(_env_file=None, LLM_PROFILE=None, LLM_PROVIDER="nvidia", DESIGN_AGENT_PROVIDER=None)).name == "nvidia"


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


@pytest.mark.parametrize("failure, attempts, code", [(400, 1, "request_rejected"), (429, 2, "provider_rate_limited"),
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
    transport = GeminiProvider(config(), client=sdk(respond), sleep=lambda _: None)
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
        assert response.status_code == (503 if degrade else 201), response.text
        run = (client.get(f"/api/v1/design-agent/runs/{response.json()['detail']['run_id']}", headers=headers).json()
               if degrade else response.json())
        assert run["provider_name"] == "gemini" and run["degraded"] is degrade
        trace = client.get(f"/api/v1/design-agent/runs/{run['id']}/trace", headers=headers).json()["items"]
        degraded = [item for item in trace if item["status"] == "degraded"]
        assert len(calls) == (2 if degrade else 3)
        assert degraded == []
        if degrade:
            assert run["status"] == "failed" and len(trace) == 1
            assert trace[0]["details"]["failure_code"] == "provider_rate_limited"
            assert trace[0]["model_name"] == "dev-env-model"
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


@pytest.fixture
def design_schemas():
    """Capture the real node builders before inference, using existing frozen controls."""
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from app.design_agent.contracts import NPCDialogueRevisionOutput
    baseline = json.loads((Path(__file__).parent / 'tests/fixtures/critic_review_controls.json').read_text())['baselines']['frostpeak']
    class Captured(BaseException):
        pass
    class Capture:
        def complete(self, request):
            self.request = request
            raise Captured()
    capture = Capture()
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    artifact, evidence = baseline['artifact'], baseline['evidence']
    review = {'objective': 'Review the frozen game design', 'design_contract_version': 2}
    calls = {
        'plan': lambda: provider.plan(review['objective'], ['frozen-document']),
        'generate_blueprint': lambda: provider.generate(review, evidence),
        'critique': lambda: provider.critique(artifact, evidence, review_request=review),
        'revise': lambda: provider.revise(artifact, evidence, 'Replace quest objective prose with spoken dialogue.',
                                         target_sections=['quest_hooks'], review_request=review),
    }
    models = {}
    for node, call in calls.items():
        with pytest.raises(Captured):
            call()
        models[node] = capture.request.response_model
    models['speech_patch'] = NPCDialogueRevisionOutput
    return models


def schema_nodes(schema):
    """Visit schema objects, not user property names or annotation values."""
    yield schema
    for key in ('properties', '$defs', 'definitions', 'patternProperties', 'dependentSchemas'):
        for child in schema.get(key, {}).values():
            yield from schema_nodes(child)
    for key in ('items', 'additionalProperties', 'contains', 'if', 'then', 'else',
                'unevaluatedProperties', 'unevaluatedItems'):
        child = schema.get(key)
        if isinstance(child, dict):
            yield from schema_nodes(child)
    for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
        for child in schema.get(key, []):
            yield from schema_nodes(child)


@pytest.mark.parametrize('node', ['plan', 'generate_blueprint', 'critique', 'revise', 'speech_patch'])
def test_gemini_schema_reduction_defaults_to_revision_only_without_mutating_full_contract(design_schemas, node):
    from app.design_agent.gemini_provider import GeminiProvider
    from app.design_agent.llm_provider import NvidiaStructuredOutputError
    full = design_schemas[node].model_json_schema()
    before = copy.deepcopy(full)
    calls = []
    def respond(r):
        calls.append(json.loads(r.content))
        return interaction('{}')
    provider = GeminiProvider(config(), client=sdk(respond))
    try:
        with pytest.raises(NvidiaStructuredOutputError):
            provider.complete(CompletionRequest('revise' if node == 'speech_patch' else node,
                              request().messages, design_schemas[node]))
        reduced = calls[0]['response_format'][0]['schema']
        assert all(call['response_format'][0]['schema'] == reduced for call in calls)
        assert full == before == design_schemas[node].model_json_schema()
        if node not in {'revise', 'speech_patch'}:
            assert reduced == full
            if node == 'generate_blueprint':
                assert reduced['$defs']['DraftDialogue']['properties']['stage']['enum'] == [
                    'greeting', 'progress', 'completion', 'failed', 'other']
            return
        types.JSONSchema.model_validate(reduced)
        assert json.loads(json.dumps(reduced)) == reduced
        forbidden = {'enum', 'const', 'pattern', 'minLength', 'maxLength', 'minItems', 'maxItems',
                     'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf',
                     'minProperties', 'maxProperties', 'uniqueItems', 'minContains', 'maxContains', 'format', 'not', 'propertyNames'}
        assert all(not forbidden.intersection(item) for item in schema_nodes(reduced))
        for original, wire in zip(schema_nodes(full), schema_nodes(reduced), strict=True):
            for key in ('type', 'required', '$ref', 'additionalProperties'):
                if key in original and not (key == 'additionalProperties' and isinstance(original[key], dict)):
                    assert wire[key] == original[key]
            assert wire.get('properties', {}).keys() == original.get('properties', {}).keys()
            if '$ref' in wire:
                target = reduced
                for part in wire['$ref'].removeprefix('#/').split('/'):
                    target = target[part.replace('~1', '/').replace('~0', '~')]
                assert isinstance(target, dict)
        assert full == before == design_schemas[node].model_json_schema()
        if node == 'revise':
            # A fixed two-quest fixture bounds decoder growth, not just removal of keyword names.
            assert len(json.dumps(reduced, separators=(',', ':')).encode()) <= 10000
            assert max(len(item.get('anyOf', [])) for item in schema_nodes(reduced)) <= 20
    finally:
        provider.close()


def test_gemini_reduction_preserves_keyword_named_properties_and_enum_only_types():
    from app.design_agent.gemini_provider import _gemini_response_schema
    full = {'type': 'object', 'properties': {
        'pattern': {'enum': ['red', 'blue'], 'not': {'enum': ['null']}},
        'minItems': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
    }, 'required': ['pattern', 'minItems'], 'additionalProperties': False}
    assert _gemini_response_schema(full) == {
        'type': 'object', 'properties': {'pattern': {'type': 'string'},
            'minItems': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['pattern', 'minItems'], 'additionalProperties': False}


@pytest.mark.parametrize('repair', [False, True])
def test_gemini_relaxed_wire_constraints_still_use_full_local_validation_and_repair(repair):
    from app.design_agent.gemini_provider import GeminiProvider
    from app.design_agent.llm_provider import NvidiaStructuredOutputError
    class FullContract(BaseModel):
        code: str = Field(min_length=2, max_length=4, pattern='^[A-Z]+$')
        count: int = Field(ge=1, le=3)
        tags: list[str] = Field(min_length=1, max_length=2)
        state: Literal['ready', 'blocked']
    invalid = {'code': 'x', 'count': 99, 'tags': [], 'state': 'invented'}
    valid = {'code': 'OK', 'count': 2, 'tags': ['source'], 'state': 'ready'}
    original = copy.deepcopy(FullContract.model_json_schema())
    calls = []
    def respond(r):
        calls.append(json.loads(r.content))
        return interaction(json.dumps(valid if repair and len(calls) == 2 else invalid))
    provider = GeminiProvider(config(), client=sdk(respond))
    req = CompletionRequest('revise', request().messages, FullContract)
    try:
        if repair:
            result = provider.complete(req)
            assert result.content == valid and result.metadata['repair_attempts'] == 1
        else:
            with pytest.raises(NvidiaStructuredOutputError):
                provider.complete(req)
        assert len(calls) == 2
        for call in calls:
            reduced = call['response_format'][0]['schema']
            types.JSONSchema.model_validate(reduced)
            assert reduced['properties'] == {
                'code': {'title': 'Code', 'type': 'string'},
                'count': {'title': 'Count', 'type': 'integer'},
                'tags': {'items': {'type': 'string'}, 'title': 'Tags', 'type': 'array'},
                'state': {'title': 'State', 'type': 'string'},
            }
            assert 'minLength' not in reduced['properties']['code']
            assert 'enum' not in reduced['properties']['state']
        assert req.response_model is FullContract and FullContract.model_json_schema() == original
    finally:
        provider.close()


def test_nvidia_guided_output_still_sends_the_full_unreduced_schema():
    from app.design_agent.llm_provider import NvidiaProvider
    class FullContract(BaseModel):
        code: str = Field(min_length=2, max_length=4, pattern='^[A-Z]+$')
        state: Literal['ready', 'blocked']
    calls = []
    def respond(r):
        calls.append(json.loads(r.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"code":"OK","state":"ready"}'}, 'finish_reason': 'stop'}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = NvidiaProvider(base_url='https://offline.invalid', timeout_seconds=1, repair_enabled=False,
                                  client=client, key_reader=lambda _: 'offline-key')
        result = provider.complete(CompletionRequest('plan', request().messages, FullContract, guided_json=True))
        assert result.content == {'code': 'OK', 'state': 'ready'}
        assert calls[0]['response_format']['json_schema']['schema'] == FullContract.model_json_schema()


@pytest.mark.parametrize(('setting', 'reduced_nodes'), [
    ('[]', set()), ('["revise"]', {'revise'}), ('["generate_blueprint"]', {'generate_blueprint'}),
])
def test_gemini_node_reduction_setting_is_honored_without_leaking_between_completions(monkeypatch, setting, reduced_nodes):
    from app.design_agent.gemini_provider import GeminiProvider
    monkeypatch.setenv('GEMINI_SCHEMA_REDUCTION_NODES', setting)
    class EnumAnswer(BaseModel):
        answer: Literal['ok', 'blocked']
    calls = []
    provider = GeminiProvider(config(), client=sdk(lambda r: calls.append(json.loads(r.content)) or interaction('{"answer":"ok"}')))
    try:
        for node in ('revise', 'plan', 'generate_blueprint', 'critique'):
            result = provider.complete(CompletionRequest(node, request().messages, EnumAnswer))
            assert result.content == {'answer': 'ok'}
            prop = calls[-1]['response_format'][0]['schema']['properties']['answer']
            assert ('enum' not in prop) is (node in reduced_nodes)
    finally:
        provider.close()
