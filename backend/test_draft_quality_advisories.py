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
    assert [a.check for a in advisories] == ['quest_label_mismatch'] * 3 + ['objective_text_copied_as_dialogue'] * 2 + ['warning_in_rules']
    assert [a.severity for a in advisories] == ['medium'] * 5 + ['low']
    assert advisories[0].values['situation'] == 'Quest 0 completion'
    assert advisories[0].values['quest_id'] == 'quest_1'
    assert advisories[0].paths == ['/npc_archetypes/content/npcs/0/dialogue_triggers/0/situation',
                                   '/npc_archetypes/content/npcs/0/dialogue_triggers/0/eligibility/quest_id']
    assert advisories[3].values['dialogue'] == 'Ｍｉｎｅ five chunks of ore!'
    assert len({a.id for a in advisories}) == 6
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


def test_persisted_advisory_evaluation_cannot_change_approval_identity_or_final(db_session):
    from app.design_agent.evaluation import save_draft_quality_evaluation
    from app.design_agent.finding_reviews import DesignFindingReviewService, content_digest
    from app.design_agent.review_policy import validate_persisted_design_approval
    from app.design_agent.service import DesignAgentService
    from app.models.design_agent import DesignAgentEvidenceSnapshot
    from test_finalize_content_integrity import saved_review
    from verify_final_integrity import verify_final_integrity

    workflow, run, artifact, critique, state = saved_review(db_session)
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
