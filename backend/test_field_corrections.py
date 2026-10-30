"""Exact field corrections, using frozen fixtures and disposable storage only."""
import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.design_agent.schemas import DesignAgentReviewRequest
from app.design_agent.content_draft import content_field_revision_model, assemble_content_field_revision
from test_design_safety_guards import review_api, review


HOOK = '/quest_hooks/content/quests/1/dialogue_hooks/0'
SITUATION = '/npc_archetypes/content/npcs/0/dialogue_triggers/1/situation'


def saved():
    return json.loads((Path(__file__).parent / 'tests/fixtures/frostpeak_b4c_reviewed.json').read_text())


def test_correction_is_a_distinct_typed_action_bound_to_exact_fields():
    request = DesignAgentReviewRequest(decision='request_correction', artifact_id=uuid4(),
        reason='Make this a spoken line without changing the objective.', target_paths=[HOOK])
    assert request.target_paths == [HOOK]
    assert request.target_sections is None


@pytest.mark.parametrize('paths', [[], [HOOK, HOOK], [HOOK] * 3,
    ['/quest_hooks/content/quests/1'], ['/quest_hooks/content/quests/1/objective'],
    ['/quest_hooks/content/quests/1/dialogue_hooks'], ['/unity_runtime_preview/content/input'],
    ['/npc_archetypes/content/npcs/0/dialogue_triggers/1/eligibility/quest_id'],
    ['/quest_hooks/content/quests/-1/dialogue_hooks/0'],
    ['/quest_hooks/content/quests/01/dialogue_hooks/0'], ['/quest_hooks/citations/0'],
    ['/quest_hooks/content/quests/0/id'], ['/npc_archetypes/content/npcs/0/dialogue_triggers/0']])
def test_invalid_scope_is_rejected_by_the_request_contract(paths):
    with pytest.raises(ValidationError):
        DesignAgentReviewRequest(decision='request_correction', artifact_id=uuid4(), reason='Fix text', target_paths=paths)


def test_filtered_model_is_tiny_and_assembly_refuses_other_fields():
    fixture = saved()
    artifact, evidence = fixture['content'], fixture['evidence']
    model = content_field_revision_model(['quest_hooks'], artifact, target_paths=[HOOK])
    schema = json.dumps(model.model_json_schema(), separators=(',', ':'))
    assert len(schema.encode()) < 1500
    patch = {'changes': [{'artifact_path': HOOK, 'replacement': 'Five chunks secured. The forge can burn again.'}]}
    result = assemble_content_field_revision(artifact, patch, ['quest_hooks'], evidence, target_paths=[HOOK])
    assert result['quest_hooks']['content']['quests'][1]['dialogue_hooks'][0] == patch['changes'][0]['replacement']
    patch['changes'][0]['artifact_path'] = '/quest_hooks/content/quests/1/reward'
    with pytest.raises(ValueError):
        assemble_content_field_revision(artifact, patch, ['quest_hooks'], evidence, target_paths=[HOOK])
    assert (content_field_revision_model(['quest_hooks'], artifact).model_json_schema()
            == content_field_revision_model(['quest_hooks'], artifact, target_paths=None).model_json_schema())
    situation_model = content_field_revision_model(['npc_archetypes'], artifact, target_paths=[SITUATION])
    for invalid in (None, {'text': 'wrong type'}, 'x' * 501):
        with pytest.raises(ValidationError):
            situation_model.model_validate({'changes': [{'artifact_path': SITUATION, 'replacement': invalid}]})


def test_exact_scope_permits_only_the_derived_manual_test_or_proposal_annotation():
    from app.design_agent.field_corrections import expected_correction, validate_correction_scope
    fixture = saved()
    before, evidence = fixture['content'], fixture['evidence']
    for path, value in [(SITUATION, 'Quest 1 progress inquiry'), (HOOK, 'Bring the sky-iron home.')]:
        candidate = expected_correction(before, {path: value}, evidence)
        validate_correction_scope(before, candidate, [path], evidence)
        with pytest.raises(ValueError, match='must materially change'):
            validate_correction_scope(before, before, [path], evidence)
        assert before == fixture['content']
        if path == SITUATION:
            line = candidate['npc_archetypes']['content']['npcs'][0]['dialogue_triggers'][1]
            assert line['situation'] in line['manual_test']
        else:
            assert candidate['quest_hooks']['content']['quests'][1]['assumptions'][-1].startswith('Generated quest ')
        for mutate in ('note', 'reward', 'unrelated', 'extra_assumption'):
            bad = copy.deepcopy(candidate)
            if mutate == 'note':
                bad['quest_hooks']['content']['quests'][0]['implementation_notes'].append('Unexpected note')
            elif mutate == 'reward':
                bad['quest_hooks']['content']['quests'][1]['reward'] = 'Unexpected reward'
            elif mutate == 'unrelated':
                bad['summary']['content']['description'] = 'Unexpected premise'
            else:
                bad['quest_hooks']['content']['quests'][1]['assumptions'].append('Unexpected assumption')
            with pytest.raises(ValueError, match='outside the selected correction'):
                validate_correction_scope(before, bad, [path], evidence)


def correction(client, run, draft, *, paths=None, reason='Correct this exact label; preserve all other content.'):
    return client.post(f'/api/v1/design-agent/runs/{run.id}/review',
        headers={'X-Game-Project-ID': run.game_project_id}, json={'decision': 'request_correction',
            'artifact_id': str(draft.id), 'reason': reason, 'target_paths': paths or [SITUATION]})


@pytest.mark.parametrize('failure', ['provider', 'schema', 'local', 'scope'])
@pytest.mark.parametrize('mode', ['inline', 'queued'])
def test_failed_correction_leaves_original_approvable_and_writes_no_reject(review_api, db_session, monkeypatch, failure, mode):
    from app.config import settings
    from app.design_agent.llm_provider import NvidiaProviderError, NvidiaStructuredOutputError
    from app.design_agent.provider import ProviderResult
    from app.design_agent.jobs import DesignAgentJobService
    from app.models.design_agent import DesignAgentReviewEvent, DesignAgentArtifact, DesignAgentNodeExecution
    client, workflow, run, draft, critique, state = review_api
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', mode)
    before, critique_before = copy.deepcopy(draft.content), copy.deepcopy(critique.content)
    def fail(*args, **kwargs):
        if failure == 'provider':
            raise NvidiaProviderError('Offline provider unavailable', code='provider_unavailable')
        if failure == 'schema':
            raise NvidiaStructuredOutputError('Invalid replacement', code='schema_validation_failed')
        if failure == 'local':
            raise ValueError('Invalid local replacement')
        from app.design_agent.field_corrections import expected_correction
        candidate = expected_correction(before, {SITUATION: 'Quest 1 progress inquiry'}, state['evidence_items'])
        candidate['summary']['content']['description'] = 'Unauthorized unrelated change'
        return ProviderResult(candidate, 'offline-scripted', provider_name='gemini')
    workflow.provider.revise = fail
    worker = DesignAgentJobService(workflow.session_factory, workflow_factory=lambda _: workflow)
    response = correction(client, run, draft)
    if mode == 'queued':
        assert response.status_code == 200, response.text
        assert worker.process_one('field-worker')
    else:
        assert response.status_code in (409, 502, 503), response.text
        assert 'No rejection was recorded' in response.text
    db_session.expire_all()
    assert run.status == 'awaiting_review' and run.revision_count == 1
    assert run.model_config['consecutive_revision_failures'] == 1
    assert draft.content == before and critique.content == critique_before
    assert db_session.query(DesignAgentArtifact).filter_by(run_id=run.id).count() == 1
    assert not db_session.query(DesignAgentReviewEvent).filter_by(run_id=run.id).count()
    reservation = db_session.query(DesignAgentNodeExecution).filter_by(run_id=run.id, node_name='correction_request').one()
    assert reservation.status == 'failed' and reservation.details['outcome'] == 'draft_unchanged'
    assert reservation.details['current_values'][SITUATION] == before['npc_archetypes']['content']['npcs'][0]['dialogue_triggers'][1]['situation']
    assert correction(client, run, draft).status_code == 409  # No replay of this request.
    with workflow._checkpointer() as saver:
        assert workflow._compile(saver).get_state(workflow._thread_config(run.id)).next == ('human_review',)
    approved = review(client, run, draft, state, approve=True)
    assert approved.status_code == 200, approved.text
    if mode == 'queued':
        assert worker.process_one('field-worker')
    db_session.expire_all()
    assert run.status == 'completed'


@pytest.mark.parametrize('gate', ['proposals', 'critique', 'degraded'])
def test_failed_correction_does_not_waive_any_existing_approval_gate(review_api, db_session, gate):
    from app.design_agent.llm_provider import NvidiaProviderError
    client, workflow, run, draft, critique, state = review_api
    def fail(*args, **kwargs):
        raise NvidiaProviderError('Offline unavailable', code='provider_unavailable')
    workflow.provider.revise = fail
    assert correction(client, run, draft).status_code == 503
    if gate == 'degraded':
        run.model_config = {**run.model_config, 'degraded': True}
        db_session.commit()
    elif gate == 'critique':
        critique.content = {**critique.content, 'verdict': 'needs_revision', 'findings': [
            {'severity': 'high', 'section': 'npc_archetypes', 'issue': 'Offline blocking dialogue defect.',
             'recommendation': 'Correct the exact situation before approval.'}]}
        db_session.commit()
    check_state = {**state, 'confirmed_proposals': []} if gate == 'proposals' else state
    assert review(client, run, draft, check_state, approve=True).status_code == 409


def test_correction_failures_are_bounded_without_consuming_saved_revisions(review_api, db_session):
    from app.design_agent.llm_provider import NvidiaStructuredOutputError
    client, workflow, run, draft, _, state = review_api
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise NvidiaStructuredOutputError('Invalid replacement', code='structured_output_invalid')
    workflow.provider.revise = fail
    for attempt in range(3):
        assert correction(client, run, draft, reason=f'Correction attempt {attempt}: clarify this label.').status_code == 502
    refused = correction(client, run, draft, reason='Another correction attempt.')
    assert refused.status_code == 409 and 'limit' in refused.text
    db_session.expire_all()
    assert run.revision_count == 1 and run.model_config['consecutive_revision_failures'] == 3
    assert calls == [1, 1, 1]
    assert review(client, run, draft, state, approve=True).status_code == 200


@pytest.mark.parametrize('tamper', ['paths', 'artifact', 'reason', 'reviewer', 'version', 'replay'])
def test_worker_fences_correction_before_touching_the_checkpoint(review_api, db_session, monkeypatch, tamper):
    from app.config import settings
    from app.design_agent.contracts import ResumeDecision
    from app.models.design_agent import DesignAgentJob, DesignAgentNodeExecution
    client, workflow, run, draft, _, _ = review_api
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', 'queued')
    assert correction(client, run, draft).status_code == 200
    job = db_session.query(DesignAgentJob).filter_by(run_id=run.id).one()
    assert len(job.idempotency_key) <= 160 and job.max_attempts == 1
    assert job.payload['target_paths'] == [SITUATION]
    decision = ResumeDecision.model_validate(job.payload)
    reservation = db_session.query(DesignAgentNodeExecution).filter_by(run_id=run.id, node_name='correction_request').one()
    if tamper == 'paths':
        decision.target_paths = [HOOK]
    elif tamper == 'artifact':
        decision.artifact_id = uuid4()
    elif tamper == 'reason':
        decision.reason = 'Altered instruction'
    elif tamper == 'reviewer':
        decision.reviewer_label = 'Another reviewer'
    elif tamper == 'version':
        reservation.details = {**reservation.details, 'artifact_version': 999}
    else:
        reservation.status = 'running'
    db_session.commit()
    with workflow._checkpointer() as saver:
        before = workflow._compile(saver).get_state(workflow._thread_config(run.id))
    with pytest.raises(ValueError, match='Stale, duplicate or altered'):
        workflow.resume(run.id, decision)
    with workflow._checkpointer() as saver:
        after = workflow._compile(saver).get_state(workflow._thread_config(run.id))
    assert before.config == after.config and after.next == ('human_review',)


@pytest.mark.parametrize('path,value', [(HOOK, 'The forge awaits your sky-iron.'), (SITUATION, 'Quest 1 progress inquiry')])
def test_real_gemini_adapter_uses_tiny_literal_schema_and_counts_the_mocked_http_attempt(db_session, monkeypatch, caplog, path, value):
    import logging
    from app.design_agent.gemini_provider import GeminiProvider, GeminiDesignAgentProvider
    from app.design_agent.field_corrections import validate_correction_scope
    from app.models.gemini_usage import GeminiDailyUsage
    from test_gemini_provider import config, sdk, interaction
    fixture = saved()
    calls = []
    model = 'field-test-' + uuid4().hex
    def respond(request):
        calls.append(json.loads(request.content))
        return interaction(json.dumps({'changes': [{'artifact_path': path, 'replacement': value}]}))
    transport = GeminiProvider(config(GEMINI_DEV_MODEL=model), client=sdk(respond))
    provider = GeminiDesignAgentProvider(llm_provider=transport)
    logger = logging.getLogger('app.design_agent.gemini_provider')
    monkeypatch.setattr(logger, 'disabled', False)
    monkeypatch.setattr(logger, 'propagate', True)
    request = {**fixture['config'], 'design_contract_version': 2,
        'resolved_decisions': [{'decision': 'Human rule: keep Windows PC.'}]}
    with caplog.at_level('INFO', logger=logger.name):
        result = provider.revise(fixture['content'], fixture['evidence'], 'Change only the chosen text, not rewards.',
            target_paths=[path], review_request=request)
    transport.close()
    assert len(calls) == 1
    schema = calls[0]['response_format'][0]['schema']
    assert len(json.dumps(schema, separators=(',', ':')).encode()) < 1500
    assert path in json.dumps(schema) and ('const' in json.dumps(schema) or 'enum' in json.dumps(schema))
    assert 'mode=keep_literals' in caplog.text and 'node=revise' in caplog.text
    assert 'Human rule: keep Windows PC.' in calls[0]['system_instruction']
    assert 'Change only the chosen text, not rewards.' in calls[0]['system_instruction']
    assert 'cited_excerpts' in calls[0]['input'] and 'current_value' in calls[0]['input']
    if path == SITUATION:
        assert 'dialogue_style' in calls[0]['input'] and 'eligibility' in calls[0]['input']
    validate_correction_scope(fixture['content'], result.content, [path], fixture['evidence'])
    assert db_session.query(GeminiDailyUsage).filter_by(model_id=model).one().requests == 1


@pytest.mark.parametrize('paths,status', [([HOOK.replace('/1/', '/99/')], 422), ([SITUATION.replace('/0/', '/99/')], 422),
    (['/quest_hooks/content/quests/0/reward'], 422)])
def test_invalid_current_scope_never_resumes_or_reserves_work(review_api, db_session, paths, status):
    from unittest.mock import Mock
    from app.models.design_agent import DesignAgentNodeExecution
    client, workflow, run, draft, _, _ = review_api
    workflow.resume = Mock(side_effect=AssertionError('Must refuse before workflow'))
    assert correction(client, run, draft, paths=paths).status_code == status
    assert not db_session.query(DesignAgentNodeExecution).filter_by(run_id=run.id, node_name='correction_request').count()


def test_stale_or_immutable_artifact_is_conflict_before_work(review_api, db_session):
    from unittest.mock import Mock
    client, workflow, run, draft, _, _ = review_api
    workflow.resume = Mock(side_effect=AssertionError('Must refuse before workflow'))
    response = correction(client, run, type('Old', (), {'id': uuid4()})())
    assert response.status_code == 409
    draft.immutable = True
    db_session.commit()
    assert correction(client, run, draft).status_code == 409


@pytest.mark.parametrize('paths', [[SITUATION], [HOOK], [HOOK, SITUATION]])
@pytest.mark.parametrize('mode', ['inline', 'queued'])
def test_saved_correction_creates_new_version_recritiques_and_can_approve(review_api, db_session, monkeypatch, paths, mode):
    from app.config import settings
    from app.design_agent.field_corrections import expected_correction, validate_correction_scope
    from app.design_agent.provider import ProviderResult
    from app.design_agent.review_policy import build_review_provenance
    from app.design_agent.jobs import DesignAgentJobService
    from app.models.design_agent import DesignAgentArtifact, DesignAgentCritique, DesignAgentReviewEvent, DesignAgentNodeExecution
    client, workflow, run, draft, critique, state = review_api
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', mode)
    before = copy.deepcopy(draft.content)
    replacements = {path: ('Quest 1 progress inquiry' if path == SITUATION else 'The forge is waiting for the sky-iron.') for path in paths}
    candidate = expected_correction(before, replacements, state['evidence_items'])
    calls = []
    def revise(artifact, evidence, reason, target_sections=None, *, review_request=None, target_paths=None):
        assert target_paths == sorted(paths)
        calls.append('revise')
        return ProviderResult(copy.deepcopy(candidate), 'offline-scripted', provider_name='gemini')
    def critique_call(artifact, evidence, *, review_request=None):
        calls.append('critique')
        raw = saved()['critique']['model_review_provenance']['model_output']
        return ProviderResult(raw, 'offline-scripted', provider_name='gemini',
            metadata={'finding_review_provenance': build_review_provenance(raw, artifact, evidence, review_request, clean=True)})
    workflow.provider.revise, workflow.provider.critique = revise, critique_call
    response = correction(client, run, draft, paths=paths)
    assert response.status_code == 200, response.text
    worker = DesignAgentJobService(workflow.session_factory, workflow_factory=lambda _: workflow)
    if mode == 'queued':
        assert worker.process_one('field-worker')
    db_session.expire_all()
    assert calls == ['revise', 'critique']
    assert run.status == 'awaiting_review' and run.revision_count == 2
    assert run.model_config['consecutive_revision_failures'] == 0
    assert not db_session.query(DesignAgentReviewEvent).filter_by(run_id=run.id).count()
    updated = db_session.query(DesignAgentArtifact).filter_by(run_id=run.id, version=3).one()
    assert updated.content == candidate and draft.content == before
    validate_correction_scope(before, updated.content, paths, state['evidence_items'])
    followup = db_session.query(DesignAgentCritique).filter_by(artifact_id=updated.id).one()
    reservation = db_session.query(DesignAgentNodeExecution).filter_by(run_id=run.id, node_name='correction_request').one()
    assert reservation.details['outcome'] == 'saved'
    assert reservation.details['dependent_changes']
    updated_state = {**state, 'confirmed_proposals': [{key: proposal[key] for key in ('section', 'record_id', 'assumption')}
        for proposal in followup.content['quality_scorecard']['unresolved_assumptions']]}
    accepted = review(client, run, updated, updated_state, approve=True)
    assert accepted.status_code == 200, accepted.text
    if mode == 'queued':
        assert worker.process_one('field-worker')
    db_session.expire_all()
    assert run.status == 'completed'
