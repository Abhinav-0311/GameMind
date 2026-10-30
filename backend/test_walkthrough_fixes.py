"""Offline regressions for the live mock walkthrough, not hosted acceptance."""
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.design_agent import get_design_agent_service
from app.config import settings
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from app.design_agent.provider import MockDesignAgentProvider
from main import app
from test_design_agent_workflow import CountingRAG, create_source, make_service
from test_nvidia_design_agent_provider import BlueprintCapturingProvider


def test_mock_frostpeak_summary_uses_exact_heading_excerpt_despite_art_first():
    source = (Path(__file__).parent / 'docs/demo/sample_gdd_frostpeak.md').read_text()
    premise = source.split('## Section 1: Game Summary & Overview\n', 1)[1].split('\n\n', 1)[0]
    art = source.split('## Section 3: Art Style Direction\n', 1)[1].split('\n\n', 1)[0]
    summary_id, art_id = str(uuid4()), str(uuid4())
    evidence = [
        {'chunk_id': art_id, 'document_id': 'frostpeak', 'chunk_index': 1,
         'content': '## Section 3: Art Style Direction\n' + art},
        {'chunk_id': summary_id, 'document_id': 'frostpeak', 'chunk_index': 0,
         'content': '## Section 1: Game Summary & Overview\n' + premise},
    ]
    summary = MockDesignAgentProvider()._extract_blueprint(evidence).summary
    assert summary.content['description'] == premise
    assert summary.citations == [summary_id]


def test_mock_heading_summary_wins_over_earlier_generic_game_paragraph():
    evidence = [
        {'chunk_id': str(uuid4()), 'document_id': 'game', 'chunk_index': 0,
         'content': 'Project North uses hand-painted scenery and cold blue lighting throughout its world.'},
        {'chunk_id': str(uuid4()), 'document_id': 'game', 'chunk_index': 1,
         'content': '## Overview\nThe player guides a stranded expedition to safety through the northern pass.'},
    ]
    summary = MockDesignAgentProvider()._extract_blueprint(evidence).summary
    assert summary.content['description'] == 'The player guides a stranded expedition to safety through the northern pass.'
    assert summary.citations == [evidence[1]['chunk_id']]


def test_mock_absent_summary_falls_back_in_source_order():
    evidence = [
        {'chunk_id': str(uuid4()), 'document_id': 'game', 'chunk_index': 1,
         'content': 'The game uses hand-painted scenery and cold blue lighting throughout its world.'},
        {'chunk_id': str(uuid4()), 'document_id': 'game', 'chunk_index': 0,
         'content': 'The player guides a stranded expedition to safety through the northern pass.'},
    ]
    summary = MockDesignAgentProvider()._extract_blueprint(evidence).summary
    assert summary.content['description'] == evidence[1]['content']
    assert summary.citations == [evidence[1]['chunk_id']]


def test_hosted_frostpeak_summary_preserves_saved_exact_source_contract():
    saved = json.loads((Path(__file__).parent / 'tests/fixtures/frostpeak_b4c_reviewed.json').read_text())
    provider = NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(saved['content'],
        source_ids={item['chunk_id']: f'S{index}' for index, item in enumerate(saved['evidence'])}))
    result = provider.generate({**saved['config'], 'design_contract_version': 2, 'objective': saved['objective']}, saved['evidence'])
    assert result.content['summary'] == {
        **saved['content']['summary'], 'confidence': 'Medium'}


@pytest.mark.parametrize('provider_name,status', [('mock', 409), ('nvidia', 502)])
def test_noop_revision_reports_provider_capability_without_changing_draft(db_session, monkeypatch, provider_name, status):
    project = 'offline_walkthrough_' + uuid4().hex
    document, chunks = create_source(db_session, project)
    provider = MockDesignAgentProvider()
    provider.name = provider_name
    service = make_service(db_session, CountingRAG(chunks), provider)
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', 'inline')
    app.dependency_overrides[get_design_agent_service] = lambda: service
    client, headers = TestClient(app), {'X-Game-Project-ID': project}
    try:
        started = client.post('/api/v1/design-agent/runs', headers=headers, json={
            'objective': 'Create a cited design draft.', 'document_ids': [str(document.id)],
            'hosted_provider_consent': True, 'defer_runtime': True})
        assert started.status_code == 201, started.text
        before = started.json()
        response = client.post(f"/api/v1/design-agent/runs/{before['id']}/review", headers=headers, json={
            'decision': 'reject', 'artifact_id': before['current_artifact']['id'],
            'target_sections': ['gameplay_systems'], 'reason': 'Populate the missing gameplay systems from the source.'})
        assert response.status_code == status, response.text
        if provider_name == 'mock':
            assert response.json()['detail'].startswith(
                'The offline provider cannot make this correction. Use a hosted provider or start a new run.')
        else:
            assert 'offline provider cannot' not in response.text
        after = client.get(f"/api/v1/design-agent/runs/{before['id']}", headers=headers).json()
        assert after['status'] == 'awaiting_review'
        assert after['revision_count'] == before['revision_count'] == 0
        assert after['consecutive_revision_failures'] == 1
        assert after['current_artifact'] == before['current_artifact']
        assert after['critique'] == before['critique']
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


@pytest.mark.parametrize('profile,legacy,override,expected', [
    ('test', 'nvidia', None, 'mock'),
    ('dev', 'nvidia', None, 'gemini'),
    ('showcase', 'mock', None, 'gemini'),
    (None, 'nvidia', 'mock', 'mock'),
    (None, 'nvidia', None, 'nvidia'),
])
def test_health_names_effective_provider_without_instantiating_it(monkeypatch, profile, legacy, override, expected):
    monkeypatch.setattr(settings, 'LLM_PROFILE', profile)
    monkeypatch.setattr(settings, 'LLM_PROVIDER', legacy)
    monkeypatch.setattr(settings, 'DESIGN_AGENT_PROVIDER', override)
    monkeypatch.setattr('app.services.rag_service.RAGService', lambda: SimpleNamespace(chroma_client=True, collection=True))
    response = TestClient(app).get('/health')
    assert response.status_code == 200
    assert response.json()['llm_provider'] == expected
    assert response.json()['ai_mode'] == ('local_demo' if expected == 'mock' else expected)
