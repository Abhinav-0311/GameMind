"""Real finalization/approval paths on disposable PostgreSQL; no hosted calls."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.design_agent import workflow as workflow_module
from app.design_agent.finding_reviews import content_digest
from app.design_agent.grounding import complete_design_critique, validate_generated_blueprint
from app.design_agent.jobs import DesignAgentJobService
from app.design_agent.review_policy import build_review_provenance
from app.design_agent.service import DesignAgentService
from app.design_agent.workflow import DesignAgentWorkflow
from app.models.blueprint import GameBlueprint
from app.models.design_agent import (DesignAgentArtifact, DesignAgentCritique, DesignAgentEvidenceSnapshot,
    DesignAgentJob, DesignAgentNodeExecution, DesignAgentRun)
from app.models.document import Document


B4C_HASH = '8c6b049ab9793c5594de8e4be45248e6644541b7ed732b71957bfc6533955817'
FIXTURE = Path(__file__).parent / 'tests/fixtures/frostpeak_b4c_reviewed.json'


def saved_review(db, *, version=2, defer=False, memory=False):
    saved = json.loads(FIXTURE.read_text())
    content, config, evidence = saved['content'], saved['config'], saved['evidence']
    config.update(design_contract_version=version, defer_runtime=defer, allow_unspecified_memory=memory)
    if defer:
        content['unity_runtime_preview'] = {'content': {}, 'citations': [], 'confidence': 'Low',
                                            'warnings': ['Runtime integration deferred.']}
        for quest in content['quest_hooks']['content']['quests']:
            quest['runtime'] = None
    if memory:
        content['npc_memory_design'] = {'content': {}, 'citations': [], 'confidence': 'Low',
                                         'warnings': ['Concrete NPC memory is unspecified; human design required.']}
    if version == 1:
        content = validate_generated_blueprint(content, evidence, require_actionable=True)
    request = {**config, 'objective': saved['objective']}
    raw = saved['critique']['model_review_provenance']['model_output']
    if version != 2 or defer or memory:
        critique = complete_design_critique(raw, content, evidence=evidence, review_request=request)
        critique['model_review_provenance'] = build_review_provenance(raw, content, evidence, request, clean=True)
    else:
        critique = saved['critique']
    project = 'final_integrity_' + uuid4().hex
    document = Document(game_project_id=project, title='Saved B4c Frostpeak GDD', content_type='text/markdown')
    db.add(document)
    db.flush()
    run = DesignAgentRun(game_project_id=project, objective=saved['objective'], document_ids=[str(document.id)],
        model_config=config, provider_name='gemini', status='approved', current_node='human_review',
        revision_count=1, max_revisions=2)
    db.add(run)
    db.flush()
    snapshot = DesignAgentEvidenceSnapshot(run_id=run.id, game_project_id=project, revision=1,
                                         query='Saved Frostpeak evidence', items=evidence)
    db.add(snapshot)
    db.flush()
    artifact = DesignAgentArtifact(run_id=run.id, game_project_id=project, evidence_snapshot_id=snapshot.id,
                                  version=2, artifact_type='revision', content=content)
    db.add(artifact)
    db.flush()
    review = DesignAgentCritique(run_id=run.id, game_project_id=project, artifact_id=artifact.id,
                                content=critique, provider_name='gemini', model_name='saved-offline-response')
    db.add(review)
    db.commit()
    confirmations = [{k:p[k] for k in ('section', 'record_id', 'assumption')}
                     for p in critique['quality_scorecard']['unresolved_assumptions']]
    state = {'run_id': str(run.id), 'game_project_id': project, 'document_ids': run.document_ids,
             'objective': run.objective, 'max_revisions': 2, 'revision_count': 1,
             'current_artifact_id': str(artifact.id), 'current_artifact_version': 2,
             'current_artifact': copy.deepcopy(content), 'evidence_snapshot_id': str(snapshot.id),
             'evidence_items': evidence, 'critique_id': str(review.id), 'critique': copy.deepcopy(critique),
             'confirmed_proposals': confirmations, 'design_contract_version': version}
    workflow = DesignAgentWorkflow(settings.DATABASE_URL, sessionmaker(bind=db.bind),
                                   provider=SimpleNamespace(name='gemini'), rag_service=object())
    return workflow, run, artifact, review, state


def test_saved_b4b_v2_final_hash_is_exactly_the_reviewed_hash(db_session):
    workflow, run, draft, review, state = saved_review(db_session)
    original_review = copy.deepcopy(review.content)
    assert content_digest(draft.content) == B4C_HASH
    assert len(draft.content['npc_archetypes']['content']['npcs'][0]['dialogue_triggers']) == 3
    workflow._finalize(state)
    db_session.expire_all()
    final = db_session.query(DesignAgentArtifact).filter_by(run_id=run.id, artifact_type='final').one()
    assert content_digest(final.content) == B4C_HASH
    assert final.immutable and final.content == draft.content
    assert review.content == original_review
    assert review.content['model_review_provenance']['artifact_sha256'] == B4C_HASH
    blueprint = db_session.get(GameBlueprint, final.blueprint_id)
    assert all(getattr(blueprint, key) == value for key, value in final.content.items())


@pytest.mark.parametrize('defer,memory', [(True, False), (False, True), (True, True)])
def test_final_metadata_exceptions_are_exact_and_do_not_rewrite_review(db_session, defer, memory):
    workflow, run, draft, review, state = saved_review(db_session, defer=defer, memory=memory)
    original = copy.deepcopy(draft.content)
    original_review = copy.deepcopy(review.content)
    workflow._finalize(state)
    db_session.expire_all()
    final = db_session.query(DesignAgentArtifact).filter_by(run_id=run.id, artifact_type='final').one()
    expected = copy.deepcopy(original)
    if defer:
        expected['unity_runtime_preview']['runtime_deferred'] = True
        expected['unity_runtime_preview']['warnings'].append(
            'Runtime integration explicitly deferred. Approved design only; no runtime release or materialization.')
    if memory:
        expected['npc_memory_design']['memory_unspecified'] = True
    assert final.content == expected
    assert draft.content == original and review.content == original_review


def test_v1_finalization_preserves_legacy_normalization(db_session):
    workflow, run, draft, _, state = saved_review(db_session, version=1)
    workflow._finalize(state)
    db_session.expire_all()
    final = db_session.query(DesignAgentArtifact).filter_by(run_id=run.id, artifact_type='final').one()
    assert final.content == draft.content
    assert any(note.startswith('Dialogue trigger proposal ') for note in
               final.content['npc_archetypes']['content']['npcs'][0]['implementation_notes'])


def test_canonical_guard_accepts_only_key_order_changes(db_session, monkeypatch):
    workflow, run, draft, _, state = saved_review(db_session)
    native = workflow_module.validate_generated_blueprint
    def reordered(*args, **kwargs):
        return dict(reversed(list(native(*args, **kwargs).items())))
    monkeypatch.setattr(workflow_module, 'validate_generated_blueprint', reordered)
    workflow._finalize(state)
    db_session.expire_all()
    final = db_session.query(DesignAgentArtifact).filter_by(run_id=run.id, artifact_type='final').one()
    assert content_digest(final.content) == content_digest(draft.content) == B4C_HASH


@pytest.mark.parametrize('mode', ['inline', 'queued'])
@pytest.mark.parametrize('section', ['summary', 'unity_runtime_preview', 'npc_memory_design', 'checkpoint'])
def test_integrity_failure_returns_to_real_review_without_saving_or_retrying(db_session, monkeypatch, mode, section):
    workflow, run, draft, critique, state = saved_review(db_session,
        defer=section == 'unity_runtime_preview', memory=section == 'npc_memory_design')
    original = copy.deepcopy(draft.content)
    review_before = copy.deepcopy(critique.content)
    with workflow._checkpointer() as saver:
        graph, config = workflow._compile(saver), workflow._thread_config(run.id)
        graph.update_state(config, state, as_node='critique')
        graph.invoke(None, config)
    db_session.expire_all()
    native = workflow_module.validate_generated_blueprint
    def altered(*args, **kwargs):
        candidate = native(*args, **kwargs)
        candidate[section]['warnings'].append('Unreviewed content inserted during finalization.')
        return candidate
    if section == 'checkpoint':
        native_finalize = workflow._finalize
        def checkpoint_changed(checkpoint_state):
            tampered = copy.deepcopy(checkpoint_state)
            tampered['current_artifact']['summary']['warnings'].append('Unreviewed checkpoint edit.')
            return native_finalize(tampered)
        monkeypatch.setattr(workflow, '_finalize', checkpoint_changed)
    else:
        monkeypatch.setattr(workflow_module, 'validate_generated_blueprint', altered)
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', mode)
    service = DesignAgentService(workflow)
    if mode == 'inline':
        with pytest.raises(HTTPException) as caught:
            service.review(db_session, run.id, run.game_project_id, 'approve', None, None,
                           artifact_id=draft.id, confirmed_proposals=state['confirmed_proposals'])
        assert caught.value.status_code == 409 and 'content differs' in caught.value.detail
    else:
        service.review(db_session, run.id, run.game_project_id, 'approve', None, None,
                       artifact_id=draft.id, confirmed_proposals=state['confirmed_proposals'])
        worker = DesignAgentJobService(workflow.session_factory, workflow_factory=lambda _: workflow)
        assert worker.process_one('offline-finalize-integrity')
        db_session.expire_all()
        job = db_session.query(DesignAgentJob).filter_by(run_id=run.id).one()
        assert job.status == 'failed' and job.attempts == 1 and 'content differs' in job.last_error
        assert not worker.process_one('offline-finalize-integrity')
    db_session.expire_all()
    assert (run.status, run.current_node, run.revision_count) == ('awaiting_review', 'human_review', 1)
    assert 'content differs' in run.last_error
    assert draft.content == original and critique.content == review_before
    assert db_session.query(DesignAgentArtifact).filter_by(run_id=run.id).count() == 1
    assert not db_session.query(GameBlueprint).filter_by(game_project_id=run.game_project_id).count()
    execution = db_session.query(DesignAgentNodeExecution).filter_by(run_id=run.id, node_name='finalize').one()
    assert execution.status == 'failed' and 'content differs' in execution.error
    with workflow._checkpointer() as saver:
        assert workflow._compile(saver).get_state(config).next == ('human_review',)
    # Retrying the same human approval after the fault is removed needs no model call.
    monkeypatch.setattr(workflow_module, 'validate_generated_blueprint', native)
    if section == 'checkpoint':
        monkeypatch.setattr(workflow, '_finalize', native_finalize)
    monkeypatch.setattr(settings, 'DESIGN_AGENT_EXECUTION_MODE', 'inline')
    completed = service.review(db_session, run.id, run.game_project_id, 'approve', None, None,
                               artifact_id=draft.id, confirmed_proposals=state['confirmed_proposals'])
    assert completed.status == 'completed'
