"""Schema/fallback regressions that need neither the SDK nor a provider socket."""
from types import SimpleNamespace
import json
import copy
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, Field

from app.config import Settings
from app.design_agent.gemini_provider import GeminiProvider, _gemini_response_schema
from app.design_agent.llm_provider import CompletionRequest, NvidiaProviderError
from app.design_agent.provider_factory import build_design_agent_provider
from app.design_agent.provider import MockDesignAgentProvider


def settings(**values):
    return Settings(_env_file=None, LLM_PROFILE='dev', GEMINI_DEV_MODEL='offline-model',
                    GEMINI_API_KEY='offline-key', **values)


config = settings


@pytest.fixture(autouse=True)
def isolated_quota(db_session, monkeypatch):
    import logging
    from app.design_agent import gemini_budget
    from app.models.gemini_usage import GeminiDailyUsage
    db_session.query(GeminiDailyUsage).delete()
    db_session.commit()
    monkeypatch.setattr(gemini_budget, 'process_window', gemini_budget.SlidingWindow())
    monkeypatch.setattr(logging.getLogger('app.design_agent.gemini_provider'), 'disabled', False)


def sdk(respond):
    """Mock only the external SDK boundary; retain real HTTP hooks/budget/validation."""
    client = httpx.Client(transport=httpx.MockTransport(respond))
    def create(**kwargs):
        response = client.post('https://offline.invalid/interactions', json=kwargs)
        if response.status_code >= 400:
            error = RuntimeError('Scripted SDK error')
            error.status_code, error.body = response.status_code, response.json()
            raise error
        return SimpleNamespace(output_text=response.json()['text'], status='completed', usage=None, steps=[])
    return SimpleNamespace(interactions=SimpleNamespace(create=create,
        sdk_configuration=SimpleNamespace(client=client, retry_config=None)), close=client.close)


def interaction(content):
    return httpx.Response(200, json={'text': content})


def request():
    return SimpleNamespace(messages=[{'role': 'system', 'content': 'Return JSON.'}])


@pytest.fixture
def design_schemas():
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    baseline = json.loads((Path(__file__).parent / 'tests/fixtures/critic_review_controls.json').read_text())['baselines']['frostpeak']
    class Captured(BaseException):
        pass
    class Capture:
        def complete(self, request):
            self.model = request.response_model
            raise Captured()
    capture = Capture()
    with pytest.raises(Captured):
        NvidiaDesignAgentProvider(llm_provider=capture).revise(baseline['artifact'], baseline['evidence'],
            'Replace quest objective prose with spoken dialogue.', target_sections=['quest_hooks'],
            review_request={'design_contract_version': 2})
    return {'revise': capture.model}


def schema_nodes(schema):
    if isinstance(schema, dict):
        yield schema
        for value in schema.values():
            yield from schema_nodes(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from schema_nodes(value)


def test_keep_literals_strips_other_constraints_recursively():
    full = {'type': 'object', 'properties': {
        'word': {'type': 'string', 'enum': ['é', 'ok'], 'pattern': '^ok$', 'minLength': 1, 'maxLength': 5},
        'number': {'type': 'integer', 'const': 2, 'minimum': 1, 'maximum': 5, 'multipleOf': 1},
        'items': {'type': 'array', 'items': {'type': 'string', 'const': 'ok'}, 'minItems': 1, 'maxItems': 3},
    }, 'required': ['word'], 'minProperties': 1, 'maxProperties': 3}
    assert _gemini_response_schema(full, keep_literals=True) == {
        'type': 'object', 'properties': {
            'word': {'type': 'string', 'enum': ['é', 'ok']},
            'number': {'type': 'integer', 'const': 2},
            'items': {'type': 'array', 'items': {'type': 'string', 'const': 'ok'}},
        }, 'required': ['word']}


def test_default_revision_exclusion_raises_instead_of_mock(monkeypatch):
    provider = build_design_agent_provider(settings())
    def failed(*args, **kwargs):
        raise NvidiaProviderError('Hosted revision failed', code='structured_output_invalid')
    monkeypatch.setattr(provider.primary, 'revise', failed)
    artifact = MockDesignAgentProvider().generate({}, []).content
    with pytest.raises(NvidiaProviderError, match='Hosted revision failed'):
        provider.revise(artifact, [], 'Clarify narrative', target_sections=['narrative_direction'])


@pytest.mark.parametrize('limit,expected_mode', [(6000, 'keep_literals'), (1, 'reduced')])
def test_wire_schema_selection_and_log_without_sdk(monkeypatch, caplog, limit, expected_mode):
    provider = GeminiProvider(settings(GEMINI_REVISE_KEEP_LITERALS_MAX_BYTES=limit))
    captured = []
    def create(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(output_text='{}', status='completed', usage=None, steps=[])
    monkeypatch.setattr(provider, '_sdk', lambda: SimpleNamespace(interactions=SimpleNamespace(create=create)))
    provider._schema_node.set('revise')
    schema = {'type': 'string', 'enum': ['é', 'ok'], 'minLength': 1}
    with caplog.at_level('INFO'):
        provider._send(config=provider.node_model_config['revise'], api_key='offline-key',
                       messages=[], max_tokens=100, guided_json_schema=schema)
    wire = captured[0]['response_format'][0]['schema']
    assert ('enum' in wire) == (expected_mode == 'keep_literals')
    assert 'minLength' not in wire
    assert f'mode={expected_mode}' in caplog.text
    assert f'bytes={len(json.dumps(wire, separators=(",", ":"), ensure_ascii=False).encode())}' in caplog.text
    assert 'offline-key' not in caplog.text

@pytest.fixture
def b3_revision():
    return json.loads((Path(__file__).parent / 'tests/fixtures/gemini_b3_revision.json').read_text())


@pytest.mark.parametrize('limit, keeps_literals', [(6000, True), (1411, True), (1410, False)])
def test_revision_adapts_literals_to_env_byte_threshold(b3_revision, design_schemas, monkeypatch, caplog, limit, keeps_literals):
    from app.design_agent.content_draft import content_field_revision_model
    from app.design_agent.gemini_provider import GeminiProvider
    from app.design_agent.llm_provider import NvidiaStructuredOutputError
    from test_design_contract_v2 import governed_artifact
    monkeypatch.setenv('GEMINI_REVISE_KEEP_LITERALS_MAX_BYTES', str(limit))
    artifact = governed_artifact()
    artifact['npc_memory_design'] = b3_revision['memory_section']
    small = content_field_revision_model(['npc_memory_design'], artifact)
    calls = []
    provider = GeminiProvider(config(), client=sdk(lambda r: calls.append(json.loads(r.content)) or interaction('{}')))
    try:
        with caplog.at_level('INFO'):
            for model in (small, design_schemas['revise']):
                with pytest.raises(NvidiaStructuredOutputError):
                    provider.complete(CompletionRequest('revise', request().messages, model))
        small_wire, large_wire = [call['response_format'][0]['schema'] for call in calls]
        assert 10000 < len(json.dumps(design_schemas['revise'].model_json_schema(), separators=(',', ':')).encode()) < 20000
        assert ('enum' in small_wire['$defs']['TypedContentFieldChange0']['properties']['artifact_path']) is keeps_literals
        assert ('const' in small_wire['$defs']['TypedContentFieldChange1']['properties']['artifact_path']) is keeps_literals
        assert len(json.dumps(small_wire, separators=(',', ':'), ensure_ascii=False).encode()) == (1411 if keeps_literals else 1190)
        assert not any({'enum', 'const'} & node.keys() for node in schema_nodes(large_wire))
        assert len(json.dumps(large_wire, separators=(',', ':')).encode()) <= 10000
        assert max(len(node.get('anyOf', [])) for node in schema_nodes(large_wire)) <= 20
        records = [record.getMessage() for record in caplog.records if 'Gemini schema' in record.getMessage()]
        assert len(records) == 2
        assert ('mode=keep_literals' if keeps_literals else 'mode=reduced') in records[0]
        assert f'bytes={1411 if keeps_literals else 1190}' in records[0]
        assert all('Faction' not in line and 'offline-key' not in line for line in records)
    finally:
        provider.close()


@pytest.mark.parametrize('node', ['plan', 'generate_blueprint', 'critique', 'revise'])
def test_configured_fallback_exclusions_leave_other_nodes_and_nvidia_unchanged(monkeypatch, node):
    from app.design_agent.provider import MockDesignAgentProvider
    from app.design_agent.llm_provider import NvidiaProviderError
    monkeypatch.setenv('DESIGN_AGENT_FALLBACK_DISABLED_NODES', json.dumps([node]))
    provider = build_design_agent_provider(config(DESIGN_AGENT_FALLBACK_TO_MOCK=True))
    method = 'generate' if node == 'generate_blueprint' else node
    def fail(*args, **kwargs):
        raise NvidiaProviderError('Hosted failure', code='provider_unavailable')
    monkeypatch.setattr(provider.primary, method, fail)
    with pytest.raises(NvidiaProviderError):
        getattr(provider, method)(*({'plan': ('objective', []), 'generate': ({}, []),
                                    'critique': ({}, []), 'revise': ({}, [], 'reason')}[method]))
    # The legacy NVIDIA wrapper is not governed by the Gemini exclusion setting.
    legacy = build_design_agent_provider(Settings(_env_file=None, LLM_PROFILE=None, LLM_PROVIDER='nvidia',
        DESIGN_AGENT_PROVIDER=None, DESIGN_AGENT_FALLBACK_TO_MOCK=True))
    monkeypatch.setattr(legacy.primary, 'revise', fail)
    original = MockDesignAgentProvider().generate({}, []).content
    result = legacy.revise(original, [], 'Improve narrative', target_sections=['narrative_direction'])
    assert result.metadata['degraded'] and result.provider_name == 'mock'


@pytest.mark.parametrize('method,args', [('plan', ('objective', [])), ('generate', ({}, [])), ('critique', ({}, []))])
def test_default_fallback_exclusion_preserves_other_gemini_nodes(monkeypatch, method, args):
    from app.design_agent.llm_provider import NvidiaProviderError
    provider = build_design_agent_provider(config(DESIGN_AGENT_FALLBACK_TO_MOCK=True))
    def fail(*args, **kwargs):
        raise NvidiaProviderError('Hosted failure', code='provider_unavailable')
    monkeypatch.setattr(provider.primary, method, fail)
    result = getattr(provider, method)(*args)
    assert result.provider_name == 'mock' and result.metadata['degraded']


@pytest.mark.parametrize('max_revisions', [1, 2])
@pytest.mark.parametrize('failure', ['b3', 'provider', 'assembly', 'unexpected', 'unexpected_primary', 'after_repair'])
def test_failed_gemini_revision_preserves_draft_and_critique_without_mock(b3_revision, db_session, monkeypatch, max_revisions, failure):
    import uuid
    from app.api.v1.design_agent import get_design_agent_service
    from app.config import settings
    from app.design_agent.provider import MockDesignAgentProvider
    from app.models.design_agent import DesignAgentArtifact, DesignAgentRun
    from test_design_contract_v2 import governed_artifact
    from test_design_agent_workflow import CountingRAG, create_source, make_service, start_run, client
    from main import app
    class Seed(MockDesignAgentProvider):
        name = 'gemini'
        def generate(self, plan, evidence):
            from dataclasses import replace
            content = governed_artifact()
            content['npc_memory_design'] = copy.deepcopy(b3_revision['memory_section'])
            for section in content.values():
                section['citations'] = [evidence[0]['chunk_id']]
                for key in ('npcs', 'quests'):
                    for record in section['content'].get(key, []):
                        record['source_chunk_ids'] = [evidence[0]['chunk_id']]
            return replace(super().generate(plan, evidence), content=content)
    calls = []
    def respond(r):
        calls.append(r)
        if failure == 'provider':
            return httpx.Response(503, json={'error': {'code': 503, 'message': 'offline failure'}})
        if failure == 'after_repair':
            return interaction('{"answer":"x"}')
        response = (b3_revision['response'] if failure == 'b3' else {'changes': [
            {'artifact_path': '/npc_memory_design/citations', 'replacement': ['not-frozen']} ]})
        return interaction(json.dumps(response))
    provider = build_design_agent_provider(config(DESIGN_AGENT_FALLBACK_TO_MOCK=failure != 'unexpected_primary'))
    primary = getattr(provider, 'primary', provider)
    transport = primary.llm_provider
    transport._client = sdk(respond)
    transport._sleep = lambda _: None
    if failure in {'unexpected', 'unexpected_primary'}:
        def unexpected(*args, **kwargs):
            raise RuntimeError('Unexpected offline revision failure')
        monkeypatch.setattr(primary, 'revise', unexpected)
    if failure == 'after_repair':
        class RepairContract(BaseModel):
            answer: str = Field(min_length=2)
        def repair_failure(*args, **kwargs):
            return transport.complete(CompletionRequest('revise', request().messages, RepairContract))
        monkeypatch.setattr(primary, 'revise', repair_failure)
    seed = Seed()
    for method in ('plan', 'generate', 'critique'):
        monkeypatch.setattr(primary, method, getattr(seed, method))
    project = 'gemini_revision_' + uuid.uuid4().hex[:8]
    document, chunks = create_source(db_session, project)
    service = make_service(db_session, CountingRAG(chunks), provider)
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', 'inline')
    try:
        started = start_run(service, document.id, project, max_revisions=max_revisions)
        url = f"/api/v1/design-agent/runs/{started['id']}"
        headers = {'X-Game-Project-ID': project}
        rejected = client.post(url + '/review', headers=headers, json={'decision': 'reject',
            'artifact_id': started['current_artifact']['id'], 'target_sections': ['npc_memory_design'],
            'reason': 'Qualify the NPC memory rule as an unspecified design proposal; preserve the source context.'})
        assert rejected.status_code == 409, rejected.text
        current = client.get(url, headers=headers).json()
        assert current['status'] == 'awaiting_review' and current['current_node'] == 'human_review'
        assert current['current_artifact'] == started['current_artifact']
        assert current['critique'] == started['critique']
        assert current['revision_count'] == 1 and not current['degraded']
        trace = client.get(url + '/trace', headers=headers).json()['items']
        failed = next(item for item in reversed(trace) if item['node_name'] == 'revise')
        assert failed['status'] == 'failed' and failed['provider_name'] == 'gemini'
        assert 'fallback_to' not in failed['details']
        if failure == 'b3':
            completion = failed['details']['provider_diagnostics']['completions'][0]
            assert completion['schema_error_count'] == 5
            assert completion['failure_kind'] == 'schema'
        assert db_session.query(DesignAgentArtifact).filter_by(run_id=uuid.UUID(started['id'])).count() == 1
        expected_calls = {'unexpected': 0, 'unexpected_primary': 0, 'provider': 3, 'after_repair': 2}.get(failure, 1)
        assert len(calls) == expected_calls
        if failure == 'after_repair':
            assert all('minLength' not in json.loads(call.content)['response_format'][0]['schema']['properties']['answer'] for call in calls)
            assert RepairContract.model_json_schema()['properties']['answer']['minLength'] == 2
        with service.workflow._checkpointer() as saver:
            state = service.workflow._compile(saver).get_state(service.workflow._thread_config(started['id']))
        assert state.values['revision_failed'] is True
        assert ('budget exhausted' in rejected.json()['detail'].lower()) is (max_revisions == 1)
        if max_revisions == 1:
            again = client.post(url + '/review', headers=headers, json={'decision': 'reject',
                'artifact_id': started['current_artifact']['id'], 'target_sections': ['npc_memory_design'],
                'reason': 'Try the focused memory correction again, preserving every unrelated section.'})
            assert again.status_code == 409
            assert len(calls) == expected_calls
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
        transport.close()
