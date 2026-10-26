"""Safety-policy regressions through the normal API and disposable database."""
import copy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.design_agent import get_design_agent_service
from app.config import settings
from app.design_agent.llm_provider import NvidiaProviderError, NvidiaStructuredOutputError
from app.design_agent.provider import ProviderResult
from app.design_agent.service import DesignAgentService
from app.models.design_agent import DesignAgentArtifact, DesignAgentNodeExecution, DesignAgentReviewEvent
from main import app
from test_finalize_content_integrity import saved_review


@pytest.fixture
def review_api(db_session, monkeypatch):
    workflow, run, draft, critique, state = saved_review(db_session)
    with workflow._checkpointer() as saver:
        graph, config = workflow._compile(saver), workflow._thread_config(run.id)
        graph.update_state(config, state, as_node='critique')
        graph.invoke(None, config)
    db_session.expire_all()
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', 'inline')
    app.dependency_overrides[get_design_agent_service] = lambda: DesignAgentService(workflow)
    try:
        yield TestClient(app), workflow, run, draft, critique, state
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def review(client, run, draft, state, *, approve=False, acknowledge=False):
    body = {'decision': 'approve' if approve else 'reject', 'artifact_id': str(draft.id)}
    if approve:
        body.update(confirmed_proposals=state['confirmed_proposals'], acknowledge_degraded=acknowledge)
    else:
        body.update(reason='Qualify the unspecified memory behavior without changing source-backed rules.',
                    target_sections=['npc_memory_design'])
    return client.post(f'/api/v1/design-agent/runs/{run.id}/review',
                       headers={'X-Game-Project-ID': run.game_project_id}, json=body)


@pytest.mark.parametrize('origin', ['run', 'execution', 'clean'])
@pytest.mark.parametrize('mode', ['inline', 'queued'])
def test_degraded_approval_requires_explicit_acknowledgement(review_api, db_session, monkeypatch, origin, mode):
    from app.design_agent.jobs import DesignAgentJobService
    client, workflow, run, draft, _, state = review_api
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', mode)
    worker = DesignAgentJobService(workflow.session_factory, workflow_factory=lambda _: workflow)
    if origin == 'run':
        run.model_config = {**run.model_config, 'degraded': True}
    elif origin == 'execution':
        db_session.add(DesignAgentNodeExecution(run_id=run.id, game_project_id=run.game_project_id,
            node_name='revise', attempt=1, status='degraded', provider_name='mock',
            model_name='mock-fallback', details={'artifact_id': str(draft.id), 'degraded': True}))
    db_session.commit()
    response = review(client, run, draft, state, approve=True)
    if origin == 'clean':
        assert response.status_code == 200, response.text
        if mode == 'queued':
            assert worker.process_one('safety-approval-worker')
        return
    assert response.status_code == 409 and 'acknowledge' in response.text.lower()
    assert not db_session.query(DesignAgentReviewEvent).filter_by(run_id=run.id).count()
    accepted = review(client, run, draft, state, approve=True, acknowledge=True)
    assert accepted.status_code == 200, accepted.text
    if mode == 'queued':
        assert worker.process_one('safety-approval-worker')
    db_session.expire_all()
    event = db_session.query(DesignAgentReviewEvent).filter_by(run_id=run.id).one()
    assert event.details['acknowledge_degraded'] is True


@pytest.mark.parametrize('value', ['true', 1])
def test_degraded_acknowledgement_is_a_strict_boolean(review_api, db_session, value):
    client, _, run, draft, _, state = review_api
    run.model_config = {**run.model_config, 'degraded': True}
    db_session.commit()
    response = review(client, run, draft, state, approve=True, acknowledge=value)
    assert response.status_code == 422
    assert not db_session.query(DesignAgentReviewEvent).filter_by(run_id=run.id).count()


def test_http_mapping_does_not_reuse_an_old_upstream_failure_at_human_review(review_api, db_session):
    _, _, run, _, _, _ = review_api
    db_session.add(DesignAgentNodeExecution(run_id=run.id, game_project_id=run.game_project_id,
        node_name='revise', attempt=1, status='failed', details={'http_status': 502}))
    db_session.commit()
    assert run.current_node == 'human_review'
    assert DesignAgentService._failure_status(db_session, run, 500) == 500


@pytest.mark.parametrize('failure,status', [('provider', 503), ('schema', 502), ('local', 502), ('unexpected', 409)])
def test_failed_revision_preserves_budget_and_has_bounded_attempts(review_api, db_session, monkeypatch, failure, status):
    client, workflow, run, draft, critique, state = review_api
    before, review_before = copy.deepcopy(draft.content), copy.deepcopy(critique.content)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        if failure == 'provider':
            raise NvidiaProviderError('Offline unavailable', code='provider_unavailable')
        if failure == 'schema':
            raise NvidiaStructuredOutputError('Offline invalid schema', code='schema_validation_failed')
        if failure == 'local':
            raise ValueError('Offline invalid generated field')
        raise RuntimeError('Unexpected offline failure')
    workflow.provider.revise = fail
    for number in range(1, 4):
        response = review(client, run, draft, state)
        assert response.status_code == status, response.text
        db_session.expire_all()
        assert run.revision_count == 1
        assert run.model_config['consecutive_revision_failures'] == number
        assert run.status == 'awaiting_review'
        assert draft.content == before and critique.content == review_before
    blocked = review(client, run, draft, state)
    assert blocked.status_code == 409 and 'failed revision' in blocked.text.lower()
    assert len(calls) == 3
    assert db_session.query(DesignAgentArtifact).filter_by(run_id=run.id).count() == 1


def test_invalid_mock_result_retains_degraded_evidence(review_api, db_session):
    _, workflow, run, _, _, state = review_api
    def result():
        return ProviderResult(content={}, provider_name='mock', model_name='fallback',
                              metadata={'degraded': True, 'fallback_to': 'mock'})
    def invalid(*args):
        raise ValueError('Offline local contract rejected fallback output')
    with pytest.raises(ValueError):
        workflow._provider_node(state, 'generate_blueprint', result, invalid)
    db_session.expire_all()
    assert run.model_config['degraded'] is True
    node = db_session.query(DesignAgentNodeExecution).filter_by(run_id=run.id, node_name='generate_blueprint').one()
    assert node.status == 'failed' and node.details['degraded'] is True


def test_queued_failed_revisions_have_distinct_bounded_attempts(review_api, db_session, monkeypatch):
    from app.design_agent.jobs import DesignAgentJobService
    from app.models.design_agent import DesignAgentJob
    client, workflow, run, draft, _, state = review_api
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', 'queued')
    monkeypatch.setattr(settings, 'DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES', 2)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise ValueError('Offline invalid revision')
    workflow.provider.revise = fail
    worker = DesignAgentJobService(workflow.session_factory, workflow_factory=lambda _: workflow)
    for count in (1, 2):
        queued = review(client, run, draft, state)
        assert queued.status_code == 200 and queued.json()['status'] == 'review_queued'
        assert worker.process_one('safety-offline-worker')
        assert not worker.process_one('safety-offline-worker')
        db_session.expire_all()
        assert run.revision_count == 1 and run.model_config['consecutive_revision_failures'] == count
    blocked = review(client, run, draft, state)
    assert blocked.status_code == 409 and len(calls) == 2
    jobs = db_session.query(DesignAgentJob).filter_by(run_id=run.id).all()
    assert len(jobs) == 2 and len({job.idempotency_key for job in jobs}) == 2
    assert all(job.status == 'failed' and job.attempts == 1 for job in jobs)


def test_successful_revision_increments_saved_budget_and_resets_failures(review_api, db_session):
    client, workflow, run, draft, _, state = review_api
    run.model_config = {**run.model_config, 'consecutive_revision_failures': 1}
    db_session.commit()
    candidate = copy.deepcopy(draft.content)
    candidate['npc_memory_design']['content']['rules'][1] += ' Do not infer any persistence implementation from these source excerpts.'
    workflow.provider.revise = lambda *args, **kwargs: ProviderResult(content=candidate,
        provider_name='gemini', model_name='offline-revision')
    workflow.provider.critique = lambda *args, **kwargs: ProviderResult(content={
        'verdict': 'ready_for_review', 'summary': 'Offline review control', 'findings': [],
        'review_mode': 'defect_detection', 'source_coverage': {key: 'covered' for key in candidate}},
        provider_name='gemini', model_name='offline-critic')
    response = review(client, run, draft, state)
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert run.revision_count == 2 and run.model_config['consecutive_revision_failures'] == 0
    assert db_session.query(DesignAgentArtifact).filter_by(run_id=run.id).count() == 2


@pytest.mark.parametrize('provider_name', ['nvidia', 'gemini'])
@pytest.mark.parametrize('failure,status', [('provider', 503), ('schema', 502), ('local', 502), ('envelope', 502)])
def test_generation_failure_http_mapping(db_session, monkeypatch, provider_name, failure, status):
    from app.design_agent.provider import MockDesignAgentProvider
    from test_design_agent_workflow import CountingRAG, create_source, make_service
    class FailingProvider(MockDesignAgentProvider):
        name = provider_name
        llm_provider = SimpleNamespace(preflight=lambda: None)
        def generate(self, *args):
            if failure == 'schema':
                raise NvidiaStructuredOutputError('Offline invalid schema', code='structured_output_invalid')
            if failure == 'local':
                raise ValueError('Offline local content validation failed')
            if failure == 'envelope':
                raise NvidiaProviderError('Offline invalid envelope', code='invalid_response_envelope')
            raise NvidiaProviderError('Offline unavailable', code='provider_unavailable')
    project = 'safety_mapping_' + uuid4().hex
    document, chunks = create_source(db_session, project)
    service = make_service(db_session, CountingRAG(chunks), FailingProvider())
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', 'inline')
    app.dependency_overrides[get_design_agent_service] = lambda: service
    try:
        response = TestClient(app).post('/api/v1/design-agent/runs', headers={'X-Game-Project-ID': project},
            json={'objective': 'Create a source-grounded design draft.', 'document_ids': [str(document.id)],
                  'hosted_provider_consent': True})
        assert response.status_code == status and response.json()['detail']['run_id'], response.text
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
