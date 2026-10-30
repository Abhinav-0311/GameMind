"""Offline advisory controls; never model output or approval evidence."""
import copy
import json
from pathlib import Path

import pytest

from app.design_agent import grounding


FIXTURES = Path(__file__).parent / 'tests/fixtures'


def synthetic():
    return {
        'npc_archetypes': {'content': {'npcs': [{'dialogue_triggers': [
            {'situation': 'Quest 0 completion', 'eligibility': {'quest_id': 'quest_1'}},
            {'situation': 'Quest 2 progress', 'eligibility': {'quest_id': 'quest_1'}},
            {'situation': 'Quest 1 progress', 'eligibility': {'quest_id': 'quest_2'}},
        ]}]}},
        'quest_hooks': {'content': {'quests': [
            {'id': 'quest_1', 'objective': 'Mine FIVE chunks of ore.', 'objectives': ['Return to camp.'],
             'dialogue_hooks': ['Ｍｉｎｅ five chunks of ore!', 'Return to camp']},
            {'id': 'quest_2', 'objective': 'Raise the flag.', 'objectives': [], 'dialogue_hooks': []},
        ]}},
        'npc_memory_design': {'content': {'rules': ['  warning: mechanics unassessed.  ']}, 'warnings': []},
    }


def test_exact_positive_controls_and_stable_ids_without_mutation():
    draft = synthetic()
    before = copy.deepcopy(draft)
    advisories = grounding.assess_draft_advisories(draft)
    assert [a.check for a in advisories] == ['quest_label_mismatch'] * 3 + ['objective_text_copied_as_dialogue'] * 2 + ['empty_quest_dialogue', 'warning_in_rules']
    assert [a.severity for a in advisories] == ['medium'] * 5 + ['low'] * 2
    assert advisories[0].values['situation'] == 'Quest 0 completion'
    assert advisories[0].values['quest_id'] == 'quest_1'
    assert advisories[0].paths == ['/npc_archetypes/content/npcs/0/dialogue_triggers/0/situation',
                                   '/npc_archetypes/content/npcs/0/dialogue_triggers/0/eligibility/quest_id']
    assert advisories[3].values['dialogue'] == 'Ｍｉｎｅ five chunks of ore!'
    assert len({a.id for a in advisories}) == 7
    assert advisories == grounding.assess_draft_advisories(draft)
    assert draft == before


def test_saved_b4b_warning_is_detected_without_changing_golden_content():
    from app.design_agent.finding_reviews import content_digest
    draft = json.loads((FIXTURES / 'frostpeak_b4c_reviewed.json').read_text())['content']
    advisories = grounding.assess_draft_advisories(draft)
    warning = next(a for a in advisories if a.check == 'warning_in_rules')
    assert warning.paths == ['/npc_memory_design/content/rules/1']
    assert warning.values['rule'] == draft['npc_memory_design']['content']['rules'][1]
    assert content_digest(draft) == '8c6b049ab9793c5594de8e4be45248e6644541b7ed732b71957bfc6533955817'


def test_saved_run_c_has_no_advisories_and_integrity_verdict_unchanged():
    from verify_final_integrity import verify_final_integrity
    saved = json.loads((FIXTURES / 'frostpeak_run_c_integrity.json').read_text())
    reviewed = saved['reviewed']
    final = {**copy.deepcopy(reviewed), **saved['final_section_overrides']}
    before = verify_final_integrity(reviewed, final, saved['frozen_settings'])
    assert grounding.assess_draft_advisories(reviewed) == []
    assert verify_final_integrity(reviewed, final, saved['frozen_settings']) == before
    assert before['verdict'] == 'EQUAL_EXCEPT_DOCUMENTED_METADATA'


@pytest.mark.parametrize('situation,quest_id', [
    ('Quest Hook 0 progress', 'quest_1'), ('quest 0 progress', 'quest_1'),
    ('Meet the player', 'quest_1'), ('Quest 0', 'missing'),
    ('Quest 1 and Quest 2', 'quest_1'), ('Quest 1', 'quest_1'),
])
def test_ambiguous_or_matching_labels_abstain(situation, quest_id):
    draft = synthetic()
    draft['npc_archetypes']['content']['npcs'][0]['dialogue_triggers'] = [
        {'situation': situation, 'eligibility': {'quest_id': quest_id}}]
    assert not any(a.check == 'quest_label_mismatch' for a in grounding.assess_draft_advisories(draft))


@pytest.mark.parametrize('rule', ['Unspecified, not assessed.', 'Unspecified, not assessed', ' WaRnInG: not specified '])
def test_explicit_warning_forms(rule):
    draft = {'npc_memory_design': {'content': {'rules': [rule]}}}
    assert [a.check for a in grounding.assess_draft_advisories(draft)] == ['warning_in_rules']


def test_shared_words_and_real_warning_mechanic_are_not_advisories():
    draft = synthetic()
    draft['npc_archetypes'] = {'content': {'npcs': []}}
    draft['quest_hooks']['content']['quests'][0]['dialogue_hooks'] = ['Bring that ore back to me.']
    draft['quest_hooks']['content']['quests'][1]['dialogue_hooks'] = ['Hold your ground.']
    draft['npc_memory_design']['content']['rules'] = ['Warn the player before deleting a save']
    assert grounding.assess_draft_advisories(draft) == []


def test_null_eligibility_and_duplicate_quest_ids_abstain():
    draft = synthetic()
    draft['npc_archetypes']['content']['npcs'][0]['dialogue_triggers'] = [
        {'situation': 'Quest 0 completion', 'eligibility': None}]
    assert not any(a.check == 'quest_label_mismatch' for a in grounding.assess_draft_advisories(draft))
    draft['npc_archetypes']['content']['npcs'][0]['dialogue_triggers'][0]['eligibility'] = {'quest_id': 'quest_1'}
    draft['quest_hooks']['content']['quests'].append(copy.deepcopy(draft['quest_hooks']['content']['quests'][0]))
    assert not any(a.check == 'quest_label_mismatch' for a in grounding.assess_draft_advisories(draft))


def more_advisory_draft():
    return {
        'npc_archetypes': {'content': {'npcs': [
            {'assumptions': ['Associated with Quest 0.'], 'dialogue_triggers': [
                {'situation': 'Check border post progress', 'eligibility': {'quest_id': 'quest_1'}}]},
            {'notes': ['Associated with Quest 1.'], 'dialogue_triggers': [
                {'situation': 'Check mining progress', 'eligibility': {'quest_id': 'quest_2'}}]},
        ]}},
        'quest_hooks': {'content': {'quests': [
            {'id': 'quest_1', 'objective': 'Clear guards and raise the flag.', 'dialogue_hooks': []},
            {'id': 'quest_2', 'objective': 'Mine 5 chunks of ore.', 'dialogue_hooks': []},
        ]}},
        'unity_runtime_preview': {'content': {'primary_input': 'Keyboard and Mouse',
            'target_platform': 'Windows PC', 'engine_version': 'Proposed engine', 'runtime_notes': ['Server note']},
            'citations': ['source']},
    }


def test_more_advisories_report_exact_values_without_changing_the_draft():
    draft = more_advisory_draft()
    before = copy.deepcopy(draft)
    advisories = grounding.assess_draft_advisories(draft,
        evidence=[{'chunk_id': 'source', 'content': 'Mine ore.'}],
        resolved_decisions=[{'decision_id': 'platform', 'decision': 'Use Windows PC.'}])
    grouped = {name: [a for a in advisories if a.check == name] for name in (
        'empty_quest_dialogue', 'quest_label_in_assumptions', 'runtime_value_without_support')}
    assert [len(v) for v in grouped.values()] == [2, 2, 1]
    assert grouped['empty_quest_dialogue'][0].severity == 'low'
    assert grouped['empty_quest_dialogue'][0].paths == ['/quest_hooks/content/quests/0/dialogue_hooks']
    labels = grouped['quest_label_in_assumptions']
    assert [a.values['quest_id'] for a in labels] == ['quest_1', 'quest_2']
    assert labels[0].values['note'] == 'Associated with Quest 0.'
    runtime = grouped['runtime_value_without_support'][0]
    assert runtime.paths == ['/unity_runtime_preview/content/primary_input']
    assert runtime.values == {'value': 'Keyboard and Mouse', 'evidence_ids': ['source'], 'decision_ids': ['platform']}
    assert 'literal-text check' in runtime.message and 'not proof' in runtime.message
    assert all(a.severity == 'medium' for a in [*labels, runtime])
    assert draft == before
    assert advisories == grounding.assess_draft_advisories(draft,
        evidence=[{'chunk_id': 'source', 'content': 'Mine ore.'}],
        resolved_decisions=[{'decision_id': 'platform', 'decision': 'Use Windows PC.'}])


@pytest.mark.parametrize('hooks', [None, '', {}, ['Spoken invitation.'], ['']])
def test_empty_dialogue_abstains_on_nonempty_or_invalid_values(hooks):
    draft = more_advisory_draft()
    for quest in draft['quest_hooks']['content']['quests']:
        quest['dialogue_hooks'] = hooks
    assert not any(a.check == 'empty_quest_dialogue' for a in grounding.assess_draft_advisories(draft))


def test_empty_dialogue_requires_explicit_list_and_nonblank_objective():
    draft = more_advisory_draft()
    first, second = draft['quest_hooks']['content']['quests']
    first.pop('dialogue_hooks')
    second['objective'] = ' '
    assert not any(a.check == 'empty_quest_dialogue' for a in grounding.assess_draft_advisories(draft))


@pytest.mark.parametrize('text', ['quest_index 0/1', 'Remembers the betrayal in Quest 2',
    'Associated with Quest 1', 'Associated with Quest 0; remembers Quest 2'])
def test_assumption_labels_abstain_on_indexes_other_mentions_and_ambiguity(text):
    draft = more_advisory_draft()
    draft['npc_archetypes']['content']['npcs'] = [draft['npc_archetypes']['content']['npcs'][0]]
    draft['npc_archetypes']['content']['npcs'][0]['assumptions'] = [text]
    assert not any(a.check == 'quest_label_in_assumptions' for a in grounding.assess_draft_advisories(draft))


@pytest.mark.parametrize('field', ['assumptions', 'notes', 'implementation_notes', 'relationship_notes'])
def test_association_recognition_is_case_insensitive_in_each_supported_note_list(field):
    draft = more_advisory_draft()
    npc = draft['npc_archetypes']['content']['npcs'][0]
    draft['npc_archetypes']['content']['npcs'] = [npc]
    npc.pop('assumptions')
    npc[field] = ['aSsOcIaTeD wItH qUeSt 0.']
    advisory, = [a for a in grounding.assess_draft_advisories(draft) if a.check == 'quest_label_in_assumptions']
    assert advisory.paths == [f'/npc_archetypes/content/npcs/0/{field}/0']
    assert advisory.values['quest_id'] == 'quest_1'


@pytest.mark.parametrize('links', [[None], ['missing'], ['quest_1', 'quest_2']])
def test_assumption_labels_require_one_resolvable_link(links):
    draft = more_advisory_draft()
    npc = draft['npc_archetypes']['content']['npcs'][0]
    draft['npc_archetypes']['content']['npcs'] = [npc]
    npc['dialogue_triggers'] = [{'situation': 'Progress', 'eligibility': {'quest_id': link}} for link in links]
    assert not any(a.check == 'quest_label_in_assumptions' for a in grounding.assess_draft_advisories(draft))
    npc['dialogue_triggers'] = [{'situation': 'Progress', 'eligibility': {'quest_id': 'quest_1'}}]
    draft['quest_hooks']['content']['quests'].append(copy.deepcopy(draft['quest_hooks']['content']['quests'][0]))
    assert not any(a.check == 'quest_label_in_assumptions' for a in grounding.assess_draft_advisories(draft))


@pytest.mark.parametrize('evidence,decisions', [
    (None, None), ([], None), (None, []),
    ([{'chunk_id': 'different', 'content': 'Other source'}], []),
])
def test_runtime_support_abstains_without_complete_frozen_context(evidence, decisions):
    assert not any(a.check == 'runtime_value_without_support' for a in grounding.assess_draft_advisories(
        more_advisory_draft(), evidence=evidence, resolved_decisions=decisions))


@pytest.mark.parametrize('value', ['Keyboard and Mouse', 'ＫＥＹＢＯＡＲＤ and mouse', False, 7])
def test_runtime_support_matches_complete_tokens_in_cited_evidence(value):
    draft = more_advisory_draft()
    draft['unity_runtime_preview']['content']['primary_input'] = value
    advisories = grounding.assess_draft_advisories(draft,
        evidence=[{'chunk_id': 'source', 'content': 'Keyboard and Mouse; false; 7.'}],
        resolved_decisions=[{'decision_id': 'platform', 'decision': 'Use Windows PC.'}])
    assert not any(a.check == 'runtime_value_without_support' for a in advisories)


def test_runtime_support_ignores_uncited_text_and_invalid_or_blank_values():
    draft = more_advisory_draft()
    context = {'evidence': [{'chunk_id': 'source', 'content': 'Keyboard choice and a Mouse.'},
                            {'chunk_id': 'uncited', 'content': 'Keyboard and Mouse'}],
               'resolved_decisions': [{'decision_id': 'platform', 'decision': 'Use Windows PC.'}]}
    assert len([a for a in grounding.assess_draft_advisories(draft, **context)
                if a.check == 'runtime_value_without_support']) == 1
    for value in (None, '', ' ', [], {}, '---'):
        draft['unity_runtime_preview']['content']['primary_input'] = value
        assert not any(a.check == 'runtime_value_without_support' for a in grounding.assess_draft_advisories(draft, **context))


def test_persisted_advisory_evaluation_cannot_change_approval_identity_or_final(db_session, monkeypatch):
    from app.design_agent.evaluation import save_draft_quality_evaluation
    from app.design_agent.finding_reviews import DesignFindingReviewService, content_digest
    from app.design_agent.review_policy import validate_persisted_design_approval
    from app.design_agent.service import DesignAgentService
    from app.models.design_agent import DesignAgentEvidenceSnapshot
    from test_finalize_content_integrity import saved_review
    from verify_final_integrity import verify_final_integrity

    workflow, run, artifact, critique, state = saved_review(db_session)
    new_advisories = grounding.assess_draft_advisories(more_advisory_draft(),
        evidence=[{'chunk_id': 'source', 'content': 'Mine ore.'}],
        resolved_decisions=[{'decision_id': 'platform', 'decision': 'Use Windows PC.'}])
    assess = grounding.assess_draft_advisories
    monkeypatch.setattr(grounding, 'assess_draft_advisories',
        lambda content, **context: assess(content, **context) + new_advisories)
    snapshot = db_session.get(DesignAgentEvidenceSnapshot, artifact.evidence_snapshot_id)
    before = copy.deepcopy((artifact.content, critique.content, state))
    identities = DesignFindingReviewService._identities(artifact, critique, snapshot)
    score = validate_persisted_design_approval(db_session, run, artifact, state['confirmed_proposals'])
    from app.design_agent.review_policy import saved_review_request
    review_request = saved_review_request(run)
    assert DesignAgentService._response(db_session, run).draft_evaluation is None
    save_draft_quality_evaluation(run, artifact)
    db_session.commit()
    response = DesignAgentService._response(db_session, run)
    assert response.draft_evaluation.artifact_id == artifact.id
    assert any(a.check == 'warning_in_rules' for a in response.draft_evaluation.advisories)
    assert {'empty_quest_dialogue', 'quest_label_in_assumptions', 'runtime_value_without_support'} <= {
        a.check for a in response.draft_evaluation.advisories}
    assert DesignFindingReviewService._identities(artifact, critique, snapshot) == identities
    assert validate_persisted_design_approval(db_session, run, artifact, state['confirmed_proposals']) == score
    assert saved_review_request(run) == review_request
    assert (artifact.content, critique.content, state) == before
    assert 'draft_quality_evaluation' in run.model_config
    result = workflow._finalize(state)
    db_session.expire_all()
    final_response = DesignAgentService._response(db_session, run)
    assert final_response.draft_evaluation.artifact_id == artifact.id
    final = final_response.current_artifact
    assert str(final.id) == result['final_artifact_id']
    assert final.immutable is True
    assert content_digest(final.content) == '8c6b049ab9793c5594de8e4be45248e6644541b7ed732b71957bfc6533955817'
    assert verify_final_integrity(artifact.content, final.content, run.model_config)['verdict'] == 'EXACT'
    brief, _ = DesignAgentService().technical_brief(db_session, run.id, run.game_project_id)
    assert 'warning_in_rules' not in brief and 'draft_quality_evaluation' not in brief
    assert all(check not in brief for check in ('empty_quest_dialogue', 'quest_label_in_assumptions', 'runtime_value_without_support'))


def test_persistence_receives_frozen_context_without_touching_it():
    from types import SimpleNamespace
    from uuid import uuid4
    from app.design_agent.evaluation import save_draft_quality_evaluation
    run = SimpleNamespace(model_config={'resolved_decisions': [
        {'decision_id': 'platform', 'decision': 'Use Windows PC.'}]})
    artifact = SimpleNamespace(id=uuid4(), content=more_advisory_draft())
    evidence = [{'chunk_id': 'source', 'content': 'Mine ore.'}]
    before = copy.deepcopy((artifact.content, run.model_config, evidence))
    save_draft_quality_evaluation(run, artifact, evidence=evidence)
    runtime = [a for a in run.model_config['draft_quality_evaluation']['advisories']
               if a['check'] == 'runtime_value_without_support']
    assert [a['values']['value'] for a in runtime] == ['Keyboard and Mouse']
    assert artifact.content == before[0] and evidence == before[2]
    assert run.model_config['resolved_decisions'] == before[1]['resolved_decisions']


def test_run_response_reports_only_its_scoped_human_evaluation(db_session):
    from app.design_agent.service import DesignAgentService
    from app.models.design_agent import DesignAgentEvaluation
    from test_finalize_content_integrity import saved_review

    _, run, _, _, _ = saved_review(db_session)
    run.status = 'completed'
    db_session.commit()
    assert DesignAgentService._response(db_session, run).has_evaluation is False
    evaluation = DesignAgentEvaluation(run_id=run.id, game_project_id=run.game_project_id,
        annotations={}, metrics=[], overall_score=0, passed=False)
    db_session.add(evaluation)
    db_session.commit()
    assert DesignAgentService._response(db_session, run).has_evaluation is True
    evaluation.game_project_id = 'other-workspace'
    db_session.commit()
    assert DesignAgentService._response(db_session, run).has_evaluation is False
