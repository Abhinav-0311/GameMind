"""Explicit design-only scope; no shared DB, hosted calls or runtime approval."""
import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.design_agent.grounding import assess_artifact_quality, complete_design_critique, validate_design_approval
from app.design_agent.review_policy import canonical_review_request
from app.design_agent.schemas import DesignAgentRunCreate
from app.services.blueprint_readiness import BlueprintReadinessService
from app.services.materializer_service import BlueprintMaterializerService
from test_revision_completeness_guards import complete_artifact
from test_design_finding_resolutions import audit_client


def deferred_artifact():
    content = complete_artifact()
    content['unity_runtime_preview'] = {'content': {}, 'citations': [], 'confidence': 'Low',
                                        'warnings': ['Runtime integration deferred by the reviewer.']}
    return content


def unspecified_memory_artifact():
    content = deferred_artifact()
    content['npc_memory_design'] = {'content': {'memory_nodes': []}, 'citations': [], 'confidence': 'Low',
                                    'warnings': ['NPC memory is unspecified; no continuity behavior is claimed.']}
    return content


def test_memory_scope_is_strict_opt_in_and_preserves_legacy_request_identity():
    from uuid import uuid4
    from pydantic import ValidationError
    payload = dict(objective='Review this game design.', document_ids=[uuid4()])
    assert DesignAgentRunCreate(**payload).allow_unspecified_memory is False
    assert DesignAgentRunCreate(**payload, allow_unspecified_memory=True).allow_unspecified_memory is True
    for value in ('true', 1):
        with pytest.raises(ValidationError):
            DesignAgentRunCreate(**payload, allow_unspecified_memory=value)
    legacy = canonical_review_request({'objective': 'Review'})
    assert canonical_review_request({**legacy, 'allow_unspecified_memory': False}) == legacy
    assert canonical_review_request({**legacy, 'allow_unspecified_memory': True}) != legacy


def test_only_explicit_empty_uncited_warned_memory_is_unassessed_not_complete():
    content = unspecified_memory_artifact()
    before = copy.deepcopy(content)
    assert not assess_artifact_quality(content, review_request={'defer_runtime': True})['passed']
    request = {'defer_runtime': True, 'allow_unspecified_memory': True}
    score = assess_artifact_quality(content, review_request=request)
    assert score['passed']
    assert score['unspecified_sections'] == ['npc_memory_design']
    assert 'npc_memory_design' not in score['assessed_sections']
    assert all('Unspecified' in metric['detail'] and 'not assessed' in metric['detail'] for metric in score['metrics'])
    raw = {'verdict': 'ready_for_review', 'summary': 'Review', 'findings': []}
    assert complete_design_critique(raw, content, review_request=request)['findings'] == []
    assert content == before
    populated = assess_artifact_quality(deferred_artifact(), review_request=request)
    assert populated['passed'] and populated['unspecified_sections'] == []
    assert 'npc_memory_design' in populated['assessed_sections']
    populated = assess_artifact_quality(deferred_artifact(), review_request=request)
    assert populated['passed'] and populated['unspecified_sections'] == []
    assert 'npc_memory_design' in populated['assessed_sections']


@pytest.mark.parametrize('change', ['populated', 'cited_empty', 'no_warning', 'blank_warning',
                                   'other_empty', 'recovered', 'model_opt_in'])
def test_memory_option_cannot_exempt_other_content_or_model_metadata(change):
    content = unspecified_memory_artifact()
    request = {'defer_runtime': True, 'allow_unspecified_memory': True}
    if change == 'populated':
        content['npc_memory_design']['content'] = {'memory_nodes': [{'fact': 'Remember the player.'}]}
    elif change == 'cited_empty':
        content['npc_memory_design']['citations'] = content['summary']['citations']
    elif change == 'no_warning':
        content['npc_memory_design']['warnings'] = []
    elif change == 'blank_warning':
        content['npc_memory_design']['warnings'] = [' ']
    elif change == 'other_empty':
        content['gameplay_systems']['content'] = {}
    elif change == 'recovered':
        content['npc_memory_design']['warnings'].append('The blueprint response required local structural recovery.')
    else:
        request.pop('allow_unspecified_memory')
        content['npc_memory_design']['memory_unspecified'] = True
    assert not assess_artifact_quality(content, review_request=request)['passed']


def test_memory_scope_preserves_independent_findings_and_does_not_upgrade_old_reviews():
    content = unspecified_memory_artifact()
    request = {'defer_runtime': True, 'allow_unspecified_memory': True}
    raw = {'verdict': 'needs_revision', 'summary': 'Source-backed omission', 'findings': [
        {'section': 'npc_memory_design', 'severity': 'high', 'issue': 'A source memory rule was omitted.',
         'recommendation': 'Restore the cited rule.'}]}
    before = copy.deepcopy(raw)
    assert complete_design_critique(raw, content, review_request=request)['findings'] == raw['findings']
    with pytest.raises(ValueError, match='Independent critique'):
        validate_design_approval(content, [], raw, review_request=request)
    old = complete_design_critique({'verdict': 'ready_for_review', 'summary': 'Old review', 'findings': []},
                                  content, review_request={'defer_runtime': True})
    with pytest.raises(ValueError):
        validate_design_approval(content, [], old, review_request=request)
    assert raw == before


@pytest.mark.parametrize('version', [1, 2])
def test_memory_policy_reaches_generation_and_independent_critic_without_a_live_provider(version):
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider
    from test_quest_state_contract import typed_artifact
    from test_design_contract_v2 import governed_artifact
    content = governed_artifact() if version == 2 else typed_artifact()
    content['npc_memory_design'] = unspecified_memory_artifact()['npc_memory_design']
    if version == 2:
        content['npc_memory_design']['content'] = {'rules': []}
    if version == 2:
        content['npc_memory_design']['content'] = {'rules': []}
    request = {'objective': 'Review this design.', 'allow_unspecified_memory': True, 'design_contract_version': version}
    capture = BlueprintCapturingProvider(content)
    NvidiaDesignAgentProvider(llm_provider=capture).generate(request, [])
    assert 'human permits NPC memory' in capture.requests[0].messages[1]['content']
    raw = {'verdict': 'ready_for_review', 'summary': 'Independent review', 'findings': []}
    if version == 2:
        raw.update(review_mode='defect_detection', source_coverage={
            key: 'not_specified' if key == 'npc_memory_design' else 'covered' for key in BLUEPRINT_SECTION_KEYS})
    capture = BlueprintCapturingProvider(raw)
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [], review_request=request)
    assert 'human permits NPC memory' in capture.requests[0].messages[1]['content']
    assert result.content['quality_scorecard']['unspecified_sections'] == ['npc_memory_design']
    assert result.metadata['finding_review_provenance']['model_output'] == raw


def test_brief_marks_only_server_marked_empty_memory_as_unassessed():
    from unittest.mock import MagicMock
    from app.services.blueprint_brief_service import BlueprintBriefService
    content = unspecified_memory_artifact()
    content['npc_memory_design']['memory_unspecified'] = True
    blueprint = SimpleNamespace(**content, title='QA design', status='approved', document_id=None,
                                source_document_ids=[], materialization_manifest=None)
    brief = BlueprintBriefService().build(MagicMock(), blueprint, 'qa')
    assert '**Unspecified—not assessed.**' in brief
    blueprint.npc_memory_design['content'] = {'memory_nodes': [{'fact': 'Remember the player.'}]}
    assert '**Unspecified—not assessed.**' not in BlueprintBriefService().build(MagicMock(), blueprint, 'qa')


def test_new_run_deferral_is_explicit_and_legacy_request_identity_is_unchanged():
    from uuid import uuid4
    payload = dict(objective='Review this game design.', document_ids=[uuid4()])
    assert DesignAgentRunCreate(**payload).defer_runtime is False
    assert DesignAgentRunCreate(**payload, defer_runtime=True).defer_runtime is True
    legacy = {'objective': 'Review', 'fresh_dialogue': False, 'dialogue_policy': None}
    assert canonical_review_request(legacy) == legacy
    assert canonical_review_request({**legacy, 'defer_runtime': False}) == legacy
    assert canonical_review_request({**legacy, 'defer_runtime': True}) != legacy


def test_only_explicit_empty_runtime_deferral_can_pass_design_quality():
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from app.design_agent.grounding import validate_generated_blueprint
    content = deferred_artifact()
    content['quest_hooks']['content']['quests'][0]['failure_states'] = ['Leave training before completing the mission.']
    evidence = [{'chunk_id': content['summary']['citations'][0], 'matched_sections': list(BLUEPRINT_SECTION_KEYS),
                 'content': 'Mira mentors the Training Sandbox. Check the route before moving. Unlock weak-password gate. Leave training before completing the mission.'}]
    content = validate_generated_blueprint(content, evidence)
    before = copy.deepcopy(content)
    assert not assess_artifact_quality(content)['passed']
    request = {'defer_runtime': True}
    proposals = [{key: item[key] for key in ('section', 'record_id', 'assumption')}
                 for item in assess_artifact_quality(content)['unresolved_assumptions']]
    score = assess_artifact_quality(content, proposals, review_request=request)
    assert score['passed'] and score['deferred_sections'] == ['unity_runtime_preview']
    ready = complete_design_critique({'verdict': 'ready_for_review', 'findings': [], 'summary': 'Reviewed'},
                                   content, review_request=request)
    assert ready['findings'] == []
    assert validate_design_approval(content, evidence, ready, proposals, review_request=request)['passed']
    assert content == before


@pytest.mark.parametrize('change', ['other_empty', 'runtime_content', 'runtime_citation', 'runtime_binding'])
def test_deferral_cannot_hide_other_missing_content_or_engine_claims(change):
    content = deferred_artifact()
    if change == 'other_empty':
        content['gameplay_systems']['content'] = {}
    elif change == 'runtime_content':
        content['unity_runtime_preview']['content'] = {'engine_id': 'invented'}
    elif change == 'runtime_citation':
        content['unity_runtime_preview']['citations'] = content['summary']['citations']
    else:
        from app.design_agent.contracts import QuestRuntimeBinding
        # A syntactically valid binding is still incompatible with design-only scope.
        content['quest_hooks']['content']['quests'][0]['runtime'] = {
            'npc_slug': 'mira', 'difficulty': 'easy', 'gold_reward': 0, 'xp_reward': 0,
            'objectives': [{'description': 'Unlock gate', 'target_type': 'gate', 'target_id': 'gate-1', 'quantity_required': 1}],
        }
        QuestRuntimeBinding.model_validate(content['quest_hooks']['content']['quests'][0]['runtime'])
    score = assess_artifact_quality(content, review_request={'defer_runtime': True})
    assert not score['passed']


def test_model_findings_and_old_reviews_are_not_silently_dismissed_by_deferral():
    content = deferred_artifact()
    raw = {'verdict': 'needs_revision', 'summary': 'Concern', 'findings': [
        {'section': 'unity_runtime_preview', 'severity': 'high', 'issue': 'Independent concern', 'recommendation': 'Review it.'}]}
    assert complete_design_critique(raw, content, review_request={'defer_runtime': True})['findings'] == raw['findings']
    old = complete_design_critique({'verdict': 'ready_for_review', 'findings': [], 'summary': 'Review'}, content)
    with pytest.raises(ValueError):
        validate_design_approval(content, [], old, review_request={'defer_runtime': True})


def test_deferred_blueprint_cannot_materialize_or_serve_even_with_old_manifest():
    from unittest.mock import MagicMock
    content = complete_artifact()
    blueprint = SimpleNamespace(**content, status='approved', materialization_manifest={
        'last_materialized_at': '2026-10-13', 'npcs': ['mira']})
    blueprint.unity_runtime_preview = {**blueprint.unity_runtime_preview, 'runtime_deferred': True}
    readiness = BlueprintReadinessService().assess(blueprint)
    assert readiness['can_materialize'] is False and readiness['can_serve_runtime'] is False
    assert readiness['runtime_release_reason'] == 'runtime_deferred'
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = blueprint
    service = BlueprintMaterializerService()
    for operation in (service.materialize_blueprint, service.get_runtime_bundle):
        with pytest.raises(HTTPException) as caught:
            operation(db, 'blueprint', 'project')
        assert caught.value.status_code == 409
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_model_metadata_cannot_opt_a_legacy_run_into_deferral():
    content = deferred_artifact()
    content['unity_runtime_preview']['runtime_deferred'] = True
    content['unity_runtime_preview']['content'] = {'defer_runtime': True}
    score = assess_artifact_quality(content)
    assert not score['passed'] and 'unity_runtime_preview' in score['unsupported_sections']
    from pydantic import ValidationError
    from uuid import uuid4
    with pytest.raises(ValidationError):
        DesignAgentRunCreate(objective='Review this game design.', document_ids=[uuid4()], defer_runtime='true')


def test_deferred_run_export_is_blocked_independently_of_frontend():
    from unittest.mock import MagicMock
    from app.design_agent.service import DesignAgentService
    service = DesignAgentService()
    service._final_blueprint = MagicMock(return_value=(
        SimpleNamespace(model_config={'defer_runtime': True}), SimpleNamespace(unity_runtime_preview={'content': {}}),
        SimpleNamespace(content={"unity_runtime_preview": {"content": {}}})))
    with pytest.raises(HTTPException) as caught:
        service.runtime_export(MagicMock(), 'run', 'project')
    assert caught.value.status_code == 409
    from app.api.v1.blueprints import export_blueprint
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        unity_runtime_preview={'content': {}, 'runtime_deferred': True})
    with pytest.raises(HTTPException) as caught:
        export_blueprint('blueprint', db, 'project')
    assert caught.value.status_code == 409
    db.commit.assert_not_called()


def test_hosted_adapter_receives_deferral_without_dismissing_independent_findings():
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider
    from test_quest_state_contract import typed_artifact
    content = typed_artifact()
    content['unity_runtime_preview'] = deferred_artifact()['unity_runtime_preview']
    capture = BlueprintCapturingProvider(content)
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    generated = provider.generate({'objective': 'Review design only', 'defer_runtime': True}, [])
    assert generated.metadata['generation_complete'] is True
    assert 'explicitly defers runtime integration' in capture.requests[0].messages[1]['content']
    raw = {'verdict': 'ready_for_review', 'findings': [], 'summary': 'Review'}
    capture = BlueprintCapturingProvider(raw)
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    reviewed = provider.critique(content, [], review_request={'defer_runtime': True})
    assert reviewed.content['findings'] == []
    assert reviewed.content['quality_scorecard']['deferred_sections'] == ['unity_runtime_preview']
    assert reviewed.metadata['finding_review_provenance']['model_output'] == raw
    from app.design_agent.provider import MockDesignAgentProvider
    local = MockDesignAgentProvider()
    local_generated = local.generate({'defer_runtime': True}, []).content
    assert local_generated['unity_runtime_preview']['content'] == {}
    assert local_generated['unity_runtime_preview']['citations'] == []
    local_reviewed = local.critique(content, [], review_request={'defer_runtime': True})
    assert local_reviewed.content['findings'] == []
    local_revised = local.revise(content, [], 'Retain the deliberate runtime deferral.',
                                 ['unity_runtime_preview'], review_request={'defer_runtime': True})
    assert local_revised.content['unity_runtime_preview']['content'] == {}


def test_workflow_keeps_deferral_in_generation_critique_and_revision_context():
    from unittest.mock import MagicMock
    from app.design_agent.workflow import DesignAgentWorkflow
    workflow = DesignAgentWorkflow.__new__(DesignAgentWorkflow)
    workflow.provider = MagicMock()
    workflow._provider_node = lambda state, node, operation, persist: operation()
    state = {'plan': {}, 'defer_runtime': True, 'allow_unspecified_memory': True, 'objective': 'Review design only',
             'current_artifact': deferred_artifact(), 'evidence_items': [],
             'rejection_reason': 'Correct quest details', 'revision_targets': ['quest_hooks']}
    before = copy.deepcopy(state)
    workflow._generate_blueprint(state)
    workflow._critique(state)
    workflow._revise(state)
    assert workflow.provider.generate.call_args.args[0]['defer_runtime'] is True
    assert workflow.provider.critique.call_args.kwargs['review_request']['defer_runtime'] is True
    assert workflow.provider.revise.call_args.kwargs['review_request']['defer_runtime'] is True
    assert workflow.provider.generate.call_args.args[0]['allow_unspecified_memory'] is True
    assert workflow.provider.critique.call_args.kwargs['review_request']['allow_unspecified_memory'] is True
    assert workflow.provider.revise.call_args.kwargs['review_request']['allow_unspecified_memory'] is True
    assert state == before


@pytest.mark.parametrize('policy', ['defer_runtime', 'allow_unspecified_memory'])
def test_persisted_deferral_is_bound_to_the_review_and_cannot_be_added_retroactively(audit_client, policy):
    from app.design_agent.review_policy import build_review_provenance, saved_review_request, validate_persisted_design_approval
    from test_finding_approval_policy import prepared
    _, db, _, run, artifact, snapshot, critique, _ = prepared(audit_client)
    run.model_config = {policy: True}
    section = 'unity_runtime_preview' if policy == 'defer_runtime' else 'npc_memory_design'
    artifact.content = {**artifact.content, section: unspecified_memory_artifact()[section]}
    request = saved_review_request(run)
    raw = {'verdict': 'ready_for_review', 'findings': [], 'summary': 'Design review'}
    critique.content = {**complete_design_critique(raw, artifact.content, evidence=snapshot.items, review_request=request),
                        'model_review_provenance': build_review_provenance(raw, artifact.content, snapshot.items, request, clean=True)}
    db.commit()  # Disposable SQLite only.
    original = copy.deepcopy(critique.content)
    proposals = [{key: item[key] for key in ('section', 'record_id', 'assumption')}
                 for item in assess_artifact_quality(artifact.content)['unresolved_assumptions']]
    assert validate_persisted_design_approval(db, run, artifact, proposals)['passed']
    run.model_config = {}  # Stored scope no longer agrees with the frozen review.
    with pytest.raises(ValueError):
        validate_persisted_design_approval(db, run, artifact, proposals)
    assert critique.content == original
