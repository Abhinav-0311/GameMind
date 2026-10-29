"""Focused Phase 3 checks; no database, provider calls or invented live results."""
import copy
import json
from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from app.design_agent.contracts import BlueprintContent, DialogueTriggerMapping, NPCDesignCandidate
from app.design_agent.grounding import assess_artifact_quality, validate_generated_blueprint
from app.design_agent.schemas import DesignAgentRunCreate
from app.design_agent.service import DesignAgentService
from app.design_agent.workflow import DesignAgentWorkflow
from test_dialogue_trigger_alignment import EVIDENCE, LINES, artifact
from test_nvidia_design_agent_provider import BlueprintCapturingProvider
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider


def frostpeak_quest_checks():
    from test_revision_completeness_guards import complete_artifact
    content = complete_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest.update(id="ash-pass", title="Reclaim the Ash Pass", reward=None,
                 objectives=["Clear the Ash Pass guards", "Raise the Northern flag at Ash Pass"],
                 implementation_notes=[
                     "Proposal - Objective: Clear the Ash Pass guards; Event: defeat all guards; "
                     "State: quest flag 'guards_cleared' set to true; Check: guards_cleared == true AND flag_raised == false",
                     "Proposal - Objective: Raise the Northern flag at Ash Pass; Event: interact with flagpole; "
                     "State: quest flag 'flag_raised' set to true; Check: flag_raised == true AND guards_cleared == false",
                 ])
    return content


def test_mirrored_quest_checks_are_blocked_even_if_proposals_are_confirmed():
    from app.design_agent.grounding import complete_design_critique, validate_design_approval
    content = frostpeak_quest_checks()
    original = copy.deepcopy(content)
    score = assess_artifact_quality(content)
    assert "Contradiction checks" in score["blockers"]
    conflict = score["quest_check_conflicts"][0]
    assert conflict["record_id"] == "ash-pass"
    assert conflict["state"] == {"guards_cleared": True, "flag_raised": True}
    results = []
    for guards, flag in [(False, False), (True, False), (False, True), (True, True)]:
        state = {"guards_cleared": guards, "flag_raised": flag}
        checks = []
        for check in conflict["checks"]:
            terms = [term.split() for term in check.split(" AND ")]
            checks.append(all(state[key] == (value == "true") for key, operator, value in terms))
        results.append(checks)
    assert results == [[False, False], [True, False], [False, True], [False, False]]
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
    assert "Contradiction checks" in assess_artifact_quality(content, confirmations)["blockers"]
    with pytest.raises(ValueError, match="Contradiction checks"):
        validate_design_approval(content, [], {"verdict": "ready_for_review", "findings": []}, confirmations)
    reviewed = complete_design_critique({"verdict": "ready_for_review", "findings": [], "summary": "Model missed it."}, content)
    assert reviewed["verdict"] == "needs_revision"
    assert any(item["severity"] == "high" and "both required flags are true" in item["issue"]
               for item in reviewed["findings"])
    assert complete_design_critique(reviewed, content) == reviewed
    assert content == original


def test_independent_checks_preserve_completion_in_both_action_orders():
    content = frostpeak_quest_checks()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest["implementation_notes"] = [note.split(" AND ", 1)[0] for note in quest["implementation_notes"]]
    quest["reward"] = "100 gold and 250 XP"
    quest["runtime"] = None
    assert not assess_artifact_quality(content)["quest_check_conflicts"]
    checks = [note.split("; Check: ")[1] for note in quest["implementation_notes"]]
    def evaluate(check, state):
        flag, operator, literal = check.split()
        assert operator == "==" and literal == "true"
        return state[flag]
    for guards, flag in [(False, False), (True, False), (False, True), (True, True)]:
        state = {"guards_cleared": guards, "flag_raised": flag}
        results = [evaluate(check, state) for check in checks]
        assert results == [guards, flag]
        assert all(results) == (guards and flag)
    for order in [("guards_cleared", "flag_raised"), ("flag_raised", "guards_cleared")]:
        state = {key: False for key in order}
        for index, key in enumerate(order):
            state[key] = True
            assert all(evaluate(check, state) for check in checks) == (index == 1)
    assert quest["reward"] == "100 gold and 250 XP" and quest["runtime"] is None
    # Stage-entry guards are not persistent objective flags; do not infer a conflict.
    stages = frostpeak_quest_checks()
    stages["quest_hooks"]["content"]["quests"][0]["implementation_notes"] = [
        note.replace("quest flag 'guards_cleared' set to true", "stage becomes guard encounter")
            .replace("quest flag 'flag_raised' set to true", "stage becomes flag encounter")
        for note in stages["quest_hooks"]["content"]["quests"][0]["implementation_notes"]]
    assert not assess_artifact_quality(stages)["quest_check_conflicts"]


def test_workflow_passes_human_request_to_independent_critique_without_mutation():
    from app.design_agent.provider import MockDesignAgentProvider
    workflow = object.__new__(DesignAgentWorkflow)
    workflow.provider = MagicMock(spec=MockDesignAgentProvider)
    workflow._provider_node = lambda state, node, operation, persist: operation()
    state = {"objective": "Greeting, progress and completion after BOTH actions. Preserve 100 gold and 250 XP.",
             "rejection_reason": "Correct the completion line.", "fresh_dialogue": True,
             "dialogue_policy": "Once per mission attempt.", "current_artifact": frostpeak_quest_checks(),
             "evidence_items": EVIDENCE}
    original = copy.deepcopy(state)
    workflow._critique(state)
    request = workflow.provider.critique.call_args.kwargs["review_request"]
    assert request == {key: state[key] for key in ("objective", "fresh_dialogue", "dialogue_policy")}
    assert workflow.provider.critique.call_args.args == (state["current_artifact"], state["evidence_items"])
    assert state == original


def test_workflow_passes_original_requirements_to_revision_without_expanding_scope():
    from app.design_agent.provider import MockDesignAgentProvider
    workflow = object.__new__(DesignAgentWorkflow)
    workflow.provider = MagicMock(spec=MockDesignAgentProvider)
    workflow._provider_node = lambda state, node, operation, persist: operation()
    state = {"objective": "Create three new lines. No extra dependencies.", "fresh_dialogue": True,
             "dialogue_policy": "Once per attempt; reset on restart.",
             "rejection_reason": "Remove invented tutorial prerequisites from scene notes.",
             "revision_targets": ["npc_archetypes", "quest_hooks"],
             "current_artifact": frostpeak_quest_checks(), "evidence_items": EVIDENCE}
    original = copy.deepcopy(state)
    workflow._revise(state)
    kwargs = workflow.provider.revise.call_args.kwargs
    assert workflow.provider.revise.call_args.args == (
        state["current_artifact"], state["evidence_items"], state["rejection_reason"],
    )
    assert kwargs["review_request"] == {key: state[key] for key in ("objective", "fresh_dialogue", "dialogue_policy")}
    assert kwargs["target_sections"] == state["revision_targets"]
    assert state == original


@pytest.mark.parametrize("target", ["npc_archetypes", "quest_hooks"])
def test_revision_fallback_forwards_original_requirements_without_mutating_them(target):
    from app.design_agent.llm_provider import NvidiaProviderError
    from app.design_agent.nvidia_provider import ResilientDesignAgentProvider
    from app.design_agent.provider import MockDesignAgentProvider
    primary = MagicMock(spec=MockDesignAgentProvider)
    primary.name = "nvidia"
    primary.revise.side_effect = NvidiaProviderError("Unavailable", code="test_unavailable")
    fallback = MockDesignAgentProvider()
    from unittest.mock import patch
    request = {"objective": "Preserve source mechanics. No extra dependencies.",
               "fresh_dialogue": True, "dialogue_policy": "Once per attempt."}
    original = copy.deepcopy(request)
    targets = [target]
    with patch.object(fallback, "revise", wraps=fallback.revise) as revise:
        result = ResilientDesignAgentProvider(primary=primary, fallback=fallback).revise(
            frostpeak_quest_checks(), [], "Correct quest integration.", targets, review_request=request)
    assert revise.call_args.kwargs["review_request"] == request
    assert primary.revise.call_args.kwargs["review_request"] == request
    assert revise.call_args.kwargs["target_sections"] == targets
    assert result.metadata["degraded"] is True
    assert result.provider_name == "mock"
    assert "review_adjustments" not in result.content[target]["content"]
    assert result.metadata["review_directive"] == "Correct quest integration."
    assert request == original


FROST_REQUEST = {
    "objective": "Create three new spoken lines for greeting the player, an Ash Pass "
    "quest-in-progress reminder, and completion after BOTH clearing the guards and raising "
    "the Northern flag. Give concrete proposed failure/restart Event/State/Check notes. "
    "Invent no extra rewards, timers, dependencies or engine IDs."
}


def frostpeak_dialogue_review(corrected=False):
    """Hand-authored regression reference, not fresh model output or playtest proof."""
    content = frostpeak_quest_checks()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest["implementation_notes"] = [note.split(" AND ", 1)[0] for note in quest["implementation_notes"]]
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["name"] = "Eldrin"
    pairs = [
        ("player_approaches", "First encounter with Eldrin at the Watchtower", "Greetings, traveler.", "Once per mission attempt; reset on mission restart."),
        ("player_returns", "Player returns after completing a task", "Speak of your progress.", "Each return; reset on mission restart."),
        ("idle_loop", "Eldrin is idle and player is nearby", "The ancient stones remember.", "Every 30 seconds."),
    ]
    if corrected:
        pairs[1] = ("quest_in_progress", "Ash Pass quest is in progress; at least one objective remains incomplete",
                    "Ash Pass is not reclaimed yet. Clear the remaining guards and raise the Northern flag.", pairs[0][3])
        pairs[2] = ("quest_completed", "Ash Pass quest completion after BOTH clearing guards and raising the Northern flag",
                    "The guards are gone, and the Northern flag flies above Ash Pass. Well done.", pairs[0][3])
        quest["implementation_notes"] += [
            "Proposal - Failure: Player dies; Event: health reaches zero; State: quest becomes failed; Check: rewards remain ungranted.",
            "Proposal - Restart: Start another attempt; Event: player selects restart; State: quest becomes active and both objective flags reset to false; Check: quest is active AND objectives are pending and neither reward nor completion is triggered.",
        ]
    npc["dialogue_triggers"] = [dict(zip(("trigger", "situation", "text", "repeat_policy"), values)) for values in pairs]
    npc["dialogue_hooks"] = [values[2] for values in pairs]
    return content


def test_request_omissions_block_even_a_ready_critic_and_confirmed_proposals():
    from app.design_agent.grounding import complete_design_critique, validate_design_approval
    content = frostpeak_dialogue_review()
    original = copy.deepcopy(content)
    ready = {"verdict": "ready_for_review", "findings": [], "summary": "Model missed the request."}
    score = assess_artifact_quality(content, review_request=FROST_REQUEST)
    assert "Request coverage" in score["blockers"]
    assert {item["code"] for item in score["request_coverage_gaps"]} == {
        "dialogue_progress", "dialogue_completion", "unrequested_timer", "failure_transition", "restart_transition",
    }
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
    with pytest.raises(ValueError, match="Request coverage"):
        validate_design_approval(content, [], ready, confirmations, review_request=FROST_REQUEST)
    reviewed = complete_design_critique(ready, content, review_request=FROST_REQUEST)
    assert reviewed["verdict"] == "needs_revision"
    assert len([item for item in reviewed["findings"] if item["severity"] == "high"]) == 5
    assert complete_design_critique(reviewed, content, review_request=FROST_REQUEST) == reviewed
    assert content == original


def test_corrected_reference_has_request_coverage_without_claiming_semantic_proof():
    content = frostpeak_dialogue_review(corrected=True)
    score = assess_artifact_quality(content, review_request=FROST_REQUEST)
    assert not score["request_coverage_gaps"]
    assert "Request coverage" not in score["blockers"]


@pytest.mark.parametrize("trigger,situation", [
    ("first_interaction", "Player first encounters Eldrin in the Watchtower"),
    ("on_first_interaction", "Player speaks to Eldrin in the Watchtower"),
    ("on-first-interaction", "Player speaks to Eldrin in the Watchtower"),
    ("on_interaction", "Player first encounters Eldrin in the Watchtower"),
])
def test_first_contact_covers_greeting_without_waiving_independent_findings(trigger, situation):
    from app.design_agent.grounding import complete_design_critique
    content = frostpeak_dialogue_review(corrected=True)
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    mapping.update(trigger=trigger, situation=situation,
                   text="The winds of time carry whispers of the Ash Pass. Speak, and I shall "
                        "lend the weight of ages to your purpose.",
                   repeat_policy="Play once per attempt; reset on explicit quest restart.")
    content["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"][0] = mapping["text"]
    before = copy.deepcopy(content)
    score = assess_artifact_quality(content, review_request=FROST_REQUEST)
    assert not score["request_coverage_gaps"]
    critic = {"verdict": "needs_revision", "summary": "Separate issue remains.", "findings": [{
        "severity": "high", "section": "quest_hooks", "issue": "Unrequested scene prerequisite.",
        "recommendation": "Remove the prerequisite.",
    }]}
    reviewed = complete_design_critique(copy.deepcopy(critic), content, review_request=FROST_REQUEST)
    assert reviewed["verdict"] == "needs_revision"
    assert reviewed["findings"] == critic["findings"]
    assert content == before


@pytest.mark.parametrize("trigger,situation", [
    ("idle_loop", "Eldrin is idle and the player is nearby"),
    ("player_returns", "Player returns after completing a task"),
    ("on_interaction", "Player speaks to Eldrin in the Watchtower"),
    ("on_interaction", "Player encounters Eldrin again in the Watchtower"),
])
def test_ordinary_interactions_do_not_cover_requested_first_greeting(trigger, situation):
    content = frostpeak_dialogue_review(corrected=True)
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    mapping.update(trigger=trigger, situation=situation)
    score = assess_artifact_quality(content, review_request=FROST_REQUEST)
    assert [gap["code"] for gap in score["request_coverage_gaps"]] == ["dialogue_greeting"]
    assert "Request coverage" in score["blockers"]


def shared_progress_review():
    """Minimal reproduction of FQA-C01, not a rewritten saved QA artifact."""
    from test_quest_state_contract import typed_artifact
    content = typed_artifact()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc.update(name="Eldrin", assumptions=["Dialogue and quest association are proposals."],
               dialogue_triggers=[{
                   "trigger": "on_ash_pass_progress_check",
                   "situation": "Ash Pass reminder while either or both actions remain incomplete",
                   "text": "The Ash Pass waits, unclaimed. Guards still breathe where they should not, "
                           "and the Northern flag lies low. Tend to both, lest the past remain buried.",
                   "repeat_policy": "Repeatable while active and incomplete; reset on explicit restart.",
               }])
    npc["dialogue_hooks"] = [npc["dialogue_triggers"][0]["text"]]
    return content


def test_first_interaction_cannot_repeat_on_every_interaction_even_after_confirmation():
    from app.design_agent.grounding import complete_design_critique, validate_design_approval
    content = shared_progress_review()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_triggers"] = [{
        "trigger": "on_first_interaction", "situation": "first greeting",
        "text": "Speak, seeker, and I shall lend the weight of ages to your purpose.",
        "repeat_policy": "Repeatable on each interaction; no reset unless quest state changes.",
    }]
    npc["dialogue_hooks"] = [npc["dialogue_triggers"][0]["text"]]
    before = copy.deepcopy(content)
    score = assess_artifact_quality(content)
    assert [gap["code"] for gap in score["request_coverage_gaps"]] == ["dialogue_repeat_eligibility"]
    ready = {"verdict": "ready_for_review", "findings": [], "summary": "Missed the conflict."}
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
    with pytest.raises(ValueError, match="Request coverage"):
        validate_design_approval(content, [], ready, confirmations)
    reviewed = complete_design_critique(ready, content)
    assert reviewed["verdict"] == "needs_revision"
    assert any(item["severity"] == "high" and "first-interaction" in item["issue"]
               for item in reviewed["findings"])
    assert complete_design_critique(reviewed, content) == reviewed
    assert content == before  # A conflict is blocked, never silently rewritten.


@pytest.mark.parametrize("trigger,situation,policy", [
    ("on_first_interaction", "first greeting", "Once per mission attempt; reset on mission restart."),
    ("on_first_interaction", "first greeting", "Never repeat on each interaction; no reset."),
    ("on_first_interaction", "first greeting", "Do not repeat on every interaction; reset on mission restart."),
    ("on_interaction", "Greeting when the player interacts", "Repeatable on each interaction; no reset."),
    ("on_first_interaction", "first greeting", "Repeatable on each interaction while the first meeting is active."),
])
def test_repeat_guard_leaves_compatible_negated_and_unknown_rules_to_review(trigger, situation, policy):
    content = shared_progress_review()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_triggers"] = [{"trigger": trigger, "situation": situation,
                                "text": "Welcome, seeker.", "repeat_policy": policy}]
    npc["dialogue_hooks"] = ["Welcome, seeker."]
    assert not assess_artifact_quality(content)["request_coverage_gaps"]


def test_manual_dialogue_check_does_not_invent_reset_or_automatic_replay():
    pair = DialogueTriggerMapping(trigger="on_first_interaction", situation="First meeting only",
                                 text="Welcome, seeker.", repeat_policy="Once ever; no reset.")
    assert "expect the line eligible again" not in pair.manual_test
    assert "recheck situation eligibility; replay is not automatic" in pair.manual_test
    assert "If suppressed with no allowed reset, verify it stays suppressed" in pair.manual_test
    assert "Action: interact" in pair.manual_test
    assert "outside this situation" in pair.manual_test and "this trigger suppressed" in pair.manual_test
    assert pair.repeat_policy == "Once ever; no reset."


def test_frostpeak_shared_progress_claim_blocks_approval_despite_confirmed_proposals():
    from app.design_agent.grounding import validate_design_approval
    content = shared_progress_review()
    before = copy.deepcopy(content)
    score = assess_artifact_quality(content)
    gaps = score["request_coverage_gaps"]
    assert [gap["code"] for gap in gaps] == ["dialogue_progress_state"]
    assert "Guards still breathe" in gaps[0]["issue"]
    assert "zero and partial" in gaps[0]["issue"]
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
    with pytest.raises(ValueError, match="Request coverage"):
        validate_design_approval(content, [], {"verdict": "ready_for_review", "findings": []}, confirmations)
    assert content == before


def saved_frostpeak_dialogue_case():
    """Replay exact selected saved fields inside the existing complete test shell."""
    from test_revision_completeness_guards import complete_artifact
    saved = json.loads((Path(__file__).parent / "tests/fixtures/frostpeak_dialogue_review.json").read_text())
    content = complete_artifact()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc.update(copy.deepcopy(saved["npc"]))
    npc["dialogue_hooks"] = [mapping["text"] for mapping in npc["dialogue_triggers"]]
    content["quest_hooks"]["content"]["quests"][0].update(copy.deepcopy(saved["quest"]))
    return saved, content


def test_saved_partial_progress_wording_blocks_approval_even_if_critic_misses_it():
    from app.design_agent.grounding import validate_design_approval
    _, content = saved_frostpeak_dialogue_case()
    before = copy.deepcopy(content)
    score = assess_artifact_quality(content)
    gaps = [gap for gap in score["request_coverage_gaps"] if gap["code"] == "dialogue_progress_state"]
    assert len(gaps) == 1 and "flag lies low" in gaps[0]["issue"]
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
    with pytest.raises(ValueError, match="Request coverage"):
        validate_design_approval(content, [], {"verdict": "ready_for_review", "findings": []}, confirmations)
    assert content == before


def test_saved_critic_is_preserved_while_missed_progress_defect_is_merged():
    saved, content = saved_frostpeak_dialogue_case()
    original = copy.deepcopy(saved["raw_critic"])
    capture = BlueprintCapturingProvider(original)
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [])
    assert result.content["findings"][0] == original["findings"][0]
    assert result.metadata["finding_review_provenance"]["model_output"] == original
    assert any(finding["severity"] == "high" and "flag lies low" in finding["issue"]
               for finding in result.content["findings"])
    payload = json.loads(capture.requests[0].messages[1]["content"].split("Input: ", 1)[1])
    assert "request_coverage_gaps" not in payload["review_context"]
    assert "manual_review" not in payload["review_context"]
    assert payload["artifact"]["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"] == saved["npc"]["dialogue_style"]


def test_manual_progress_proposal_keeps_mirrors_aligned_without_rewriting_source_voice():
    saved, content = saved_frostpeak_dialogue_case()
    before = copy.deepcopy(content)
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    quest = content["quest_hooks"]["content"]["quests"][0]
    line = saved["proposed_progress_line"]
    npc["dialogue_triggers"][1]["text"] = line
    npc["dialogue_hooks"][1] = line
    quest["dialogue_hooks"][1] = line
    assert not any(gap["code"] == "dialogue_progress_state"
                   for gap in assess_artifact_quality(content)["request_coverage_gaps"])
    assert npc["dialogue_style"] == before["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"]
    assert quest["state_contract"] == before["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert quest["reward"] == "100 gold and 250 XP" and quest["runtime"] is None
    assert all(content[section] == before[section] for section in content if section not in {"npc_archetypes", "quest_hooks"})
    # This is a human-authored candidate, not fresh NVIDIA semantic acceptance.


def test_progress_mismatch_is_merged_after_independent_critique_without_censoring_it():
    content = shared_progress_review()
    finding = {"severity": "low", "section": "npc_archetypes", "issue": "Independent voice concern",
               "recommendation": "Review the voice."}
    capture = BlueprintCapturingProvider({"verdict": "ready_for_review", "findings": [finding], "summary": "Review"})
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [])
    payload = json.loads(capture.requests[0].messages[1]["content"].split("Input: ", 1)[1])
    assert "request_coverage_gaps" not in payload["review_context"]
    assert result.content["findings"][0] == finding
    assert any(item["severity"] == "high" and "zero and partial" in item["issue"]
               for item in result.content["findings"])
    assert result.content["verdict"] == "needs_revision"
    from app.design_agent.grounding import complete_design_critique
    assert complete_design_critique(result.content, content) == result.content


@pytest.mark.parametrize("line", [
    "Only one task remains unfinished.", "Both objectives remain incomplete.",
    "The guards are cleared; return when the Northern flag is raised.",
    "The guards are cleared, return when the Northern flag is raised.",
    "Guards defeated, but the flag still lies lowered.",
])
def test_shared_progress_does_not_claim_a_fixed_remaining_count(line):
    content = shared_progress_review()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_triggers"][0]["text"] = line
    npc["dialogue_hooks"] = [line]
    assert "dialogue_progress_state" in {gap["code"] for gap in assess_artifact_quality(content)["request_coverage_gaps"]}


@pytest.mark.parametrize("line", [
    "The oath remains unfulfilled. See that the Pass is secured before you return.",
    "Return when the guards are cleared and the Northern flag is raised.",
    "Come back once the guards are cleared and the Northern flag is raised.",
    "Wait until the guards are cleared and the Northern flag is raised.",
    "If guards still breathe, clear them. If the Northern flag lies low, raise it.",
    "Do guards still breathe? Is the Northern flag raised? Attend to whatever remains.",
    "Clear any remaining guards and raise the flag if it is not yet raised.",
])
def test_shared_progress_guard_keeps_neutral_conditional_question_and_instruction_lines(line):
    content = shared_progress_review()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_triggers"][0]["text"] = line
    npc["dialogue_hooks"] = [line]
    assert not assess_artifact_quality(content)["request_coverage_gaps"]


def test_progress_guard_does_not_guess_quest_association_or_narrow_state_eligibility():
    content = shared_progress_review()
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    mapping["situation"] = "Reminder only before either objective has been completed"
    assert not assess_artifact_quality(content)["request_coverage_gaps"]
    mapping["situation"] = "Ash Pass reminder while either or both actions remain incomplete"
    other = copy.deepcopy(content["quest_hooks"]["content"]["quests"][0])
    other.update(id="another", title="Another quest")
    content["quest_hooks"]["content"]["quests"].append(other)
    assert not assess_artifact_quality(content)["request_coverage_gaps"]


@pytest.mark.parametrize("human_request", [
    None, {"objective": "Review the lore and economy."},
    {"objective": "Write dialogue without greeting, quest-in-progress reminders or completion lines. No restart notes needed."},
])
def test_request_checks_do_not_invent_unrequested_dialogue_or_restart_requirements(human_request):
    assert not assess_artifact_quality(frostpeak_dialogue_review(), review_request=human_request)["request_coverage_gaps"]


def test_critic_findings_are_preserved_and_local_request_gaps_are_merged_after_review():
    content = frostpeak_dialogue_review()
    finding = {"severity": "high", "section": "quest_hooks", "issue": "Inspect the reward claim.", "recommendation": "Read Hook 1."}
    capture = BlueprintCapturingProvider({"verdict": "ready_for_review", "findings": [finding], "summary": "Review."})
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, EVIDENCE, review_request=FROST_REQUEST)
    payload = json.loads(capture.requests[0].messages[1]["content"].split("Input: ", 1)[1])
    assert "request_coverage_gaps" not in payload["review_context"]
    assert len(result.content["quality_scorecard"]["request_coverage_gaps"]) == 5
    assert len(result.content["findings"]) == 6
    assert result.content["findings"][0] == finding
    assert result.content["verdict"] == "needs_revision"


def test_request_timer_check_keeps_a_cited_interval_and_does_not_treat_it_as_semantic_proof():
    content = frostpeak_dialogue_review()
    source_id = content["npc_archetypes"]["content"]["npcs"][0]["source_chunk_ids"][0]
    evidence = [{"chunk_id": source_id, "content": "Eldrin's idle reminder repeats every 30 seconds."}]
    score = assess_artifact_quality(content, review_request=FROST_REQUEST, evidence=evidence)
    assert "unrequested_timer" not in {item["code"] for item in score["request_coverage_gaps"]}
    assert "Request coverage" in score["blockers"]  # Other missing requirements remain.
    absolute_ban = {"objective": "No timers."}
    assert "unrequested_timer" in {item["code"] for item in assess_artifact_quality(
        content, review_request=absolute_ban, evidence=evidence)["request_coverage_gaps"]}
    content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][2]["repeat_policy"] = "Once per attempt; never repeat every 30 seconds."
    assert not assess_artifact_quality(content, review_request=absolute_ban)["request_coverage_gaps"]


@pytest.mark.parametrize("boundary", ["api_inline", "api_queued", "worker_review", "finalize"])
def test_saved_human_request_is_enforced_at_every_approval_boundary(boundary, monkeypatch):
    from app.config import settings
    from app.design_agent import workflow as workflow_module
    from app.models.design_agent import DesignAgentArtifact, DesignAgentCritique, DesignAgentEvidenceSnapshot

    content = frostpeak_dialogue_review()
    saved = SimpleNamespace(id=uuid4(), content=content, evidence_snapshot_id=uuid4())
    run = SimpleNamespace(id=uuid4(), objective=FROST_REQUEST["objective"], provider_name="nvidia",
                          game_project_id="qa", status="awaiting_review", model_config={})
    saved.run_id, saved.game_project_id, saved.immutable, saved.artifact_type = run.id, "qa", False, "draft"
    ready = {"verdict": "ready_for_review", "findings": []}
    rows = {DesignAgentArtifact: saved, DesignAgentEvidenceSnapshot: SimpleNamespace(items=[]),
            DesignAgentCritique: SimpleNamespace(content=ready, provider_name="nvidia")}
    db = MagicMock()
    def query(model):
        result = MagicMock()
        result.filter.return_value = result.order_by.return_value = result
        result.first.return_value = rows.get(model)
        return result
    db.query.side_effect = query
    if boundary.startswith("api_"):
        transport = MagicMock()
        service = DesignAgentService(transport)
        service._get_run = lambda *_args: run
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", boundary.removeprefix("api_"))
        with pytest.raises(HTTPException, match="Request coverage") as failure:
            service.review(db, run.id, "qa", "approve", None, None, artifact_id=saved.id)
        assert failure.value.status_code == 409
        transport.resume.assert_not_called()
        db.commit.assert_not_called()
    else:
        workflow = object.__new__(DesignAgentWorkflow)
        workflow._session = lambda: nullcontext(db)
        workflow._load_run = lambda *_args: run
        workflow._begin_execution = lambda *_args, **_kwargs: SimpleNamespace(id=uuid4())
        workflow._fail_execution = MagicMock()
        workflow._complete_execution = MagicMock()
        # Checkpoint text cannot weaken the original persisted human request.
        state = {"objective": "Only review lore.", "run_id": str(run.id), "current_artifact": content,
                 "current_artifact_id": str(saved.id), "current_artifact_version": 1,
                 "evidence_items": [], "critique": ready}
        if boundary == "worker_review":
            monkeypatch.setattr(workflow_module, "interrupt", lambda _: {"decision": "approve", "artifact_id": str(saved.id)})
            method = workflow._human_review
        else:
            # The idempotent final lookup is empty; the current draft still exists.
            original_query = db.query.side_effect
            artifact_queries = iter([None, saved])
            def final_query(model):
                result = original_query(model)
                if model is DesignAgentArtifact:
                    result.first.return_value = next(artifact_queries)
                return result
            db.query.side_effect = final_query
            method = workflow._finalize
        with pytest.raises(ValueError, match="Request coverage"):
            method(state)
        db.add.assert_not_called()


def test_requested_combined_success_needs_one_concrete_check_using_the_recorded_flags():
    content = frostpeak_dialogue_review(corrected=True)
    quest = content["quest_hooks"]["content"]["quests"][0]
    request = {"objective": FROST_REQUEST["objective"] + " Final success must require both recorded actions."}
    score = assess_artifact_quality(content, review_request=request)
    assert "completion_transition" in {item["code"] for item in score["request_coverage_gaps"]}
    note = ("Proposal - Completion: Reclaim Ash Pass; Event: either required action updates its record; "
            "State: quest becomes complete and the source reward is granted once; "
            "Check: guards_cleared == true AND flag_raised == true")
    quest["implementation_notes"].append(note)
    assert not assess_artifact_quality(content, review_request=request)["request_coverage_gaps"]
    for wrong in ("guards_cleared == true OR flag_raised == true", "guards_cleared_flag == true AND flag_raised_flag == true"):
        quest["implementation_notes"][-1] = note.split("Check:")[0] + "Check: " + wrong
        assert "completion_flags" in {item["code"] for item in assess_artifact_quality(content, review_request=request)["request_coverage_gaps"]}


def frostpeak_four_request_reference():
    """Observed mapping/transition excerpts from QA run aba6ce88, not a new generation."""
    content = frostpeak_dialogue_review(corrected=True)
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest.update(id="reclaim_ash_pass", objectives=["Clear the guards", "Raise the Northern flag"],
                 implementation_notes=[
                     "Proposal - Objective: Clear the guards; Event: Player defeats all enemy NPCs in Ash Pass guard patrol; State: guards_cleared set to true; Check: guards_cleared == true",
                     "Proposal - Objective: Raise the Northern flag; Event: Player interacts with flagpole at Northern position in Ash Pass; State: flag_raised set to true; Check: flag_raised == true",
                     "Proposal - Failure: Player dies or abandons quest during Ash Pass objectives; Event: Player health reaches zero or quest abandoned via menu; State: guards_cleared and flag_raised set to false; Check: guards_cleared == false AND flag_raised == false",
                     "Proposal - Restart: Player restarts quest from failure or abandonment; Event: Player selects 'Restart Quest' or reloads checkpoint; State: guards_cleared and flag_raised set to false; Check: guards_cleared == false AND flag_raised == false",
                     "Proposal - Completion: Reclaim Ash Pass; Event: Player raises Northern flag after clearing guards; State: quest_state set to completed; Check: guards_cleared == true AND flag_raised == true",
                 ])
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][2]
    mapping.update(trigger="ash_pass_complete",
                   situation="Player has both cleared guards and raised the Northern flag in Ash Pass")
    return content


def test_saved_qa_quest_scoped_completion_is_not_reported_missing():
    content = frostpeak_four_request_reference()
    original = copy.deepcopy(content)
    codes = {item["code"] for item in assess_artifact_quality(content, review_request=FROST_REQUEST)["request_coverage_gaps"]}
    assert "dialogue_completion" not in codes
    assert content == original


@pytest.mark.parametrize("trigger,situation", [
    ("unrelated_task_complete", "Player returns after completing a task"),
    ("ash_pass_not_complete", "Ash Pass is not complete"),
    ("ash_pass_complete", "Ash Pass is not yet complete"),
    ("ash_pass_in_progress", "Player will complete Ash Pass later"),
])
def test_completion_match_does_not_accept_unrelated_negative_or_future_labels(trigger, situation):
    content = frostpeak_four_request_reference()
    content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][2].update(trigger=trigger, situation=situation)
    codes = {item["code"] for item in assess_artifact_quality(content, review_request=FROST_REQUEST)["request_coverage_gaps"]}
    assert "dialogue_completion" in codes


def test_saved_qa_requires_completion_reevaluation_and_restart_reactivation():
    from app.design_agent.grounding import complete_design_critique, validate_design_approval
    content = frostpeak_four_request_reference()
    human_request = {"objective": FROST_REQUEST["objective"] + " Final success must require both recorded actions."}
    score = assess_artifact_quality(content, review_request=human_request)
    assert {item["code"] for item in score["request_coverage_gaps"]} == {"completion_event", "restart_reactivation"}
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
    with pytest.raises(ValueError, match="Request coverage"):
        validate_design_approval(content, [], {"verdict": "ready_for_review", "findings": []},
                                 confirmations, review_request=human_request)
    original_finding = {"severity": "medium", "section": "npc_archetypes", "issue": "Review Eldrin's voice.", "recommendation": "Narrative review."}
    reviewed = complete_design_critique({"verdict": "ready_for_review", "findings": [original_finding], "summary": "Review."},
                                       content, review_request=human_request)
    assert reviewed["findings"][0] == original_finding
    assert reviewed["verdict"] == "needs_revision"
    assert complete_design_critique(reviewed, content, review_request=human_request) == reviewed


def test_manual_transition_correction_covers_both_orders_and_checks_same_active_state():
    content = frostpeak_four_request_reference()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest["implementation_notes"][3] = (
        "Proposal - Restart: New attempt; Event: player selects restart; "
        "State: quest_state set to active and guards_cleared and flag_raised set to false; "
        "Check: quest_state == active AND guards_cleared == false AND flag_raised == false")
    quest["implementation_notes"][4] = (
        "Proposal - Completion: Reclaim Ash Pass; Event: either required action updates its record; "
        "State: quest_state set to completed; Check: guards_cleared == true AND flag_raised == true")
    human_request = {"objective": FROST_REQUEST["objective"] + " Final success must require both recorded actions."}
    assert not assess_artifact_quality(content, review_request=human_request)["request_coverage_gaps"]
    # This walkthrough exercises the declared reference contract, not a Unity runtime.
    for order in [("guards_cleared", "flag_raised"), ("flag_raised", "guards_cleared")]:
        state = dict(quest_state="failed", guards_cleared=True, flag_raised=True)
        state.update(quest_state="active", guards_cleared=False, flag_raised=False)
        assert state == dict(quest_state="active", guards_cleared=False, flag_raised=False)
        for index, flag in enumerate(order):
            state[flag] = True
            if state["quest_state"] == "active" and state["guards_cleared"] and state["flag_raised"]:
                state["quest_state"] = "completed"
            assert (state["quest_state"] == "completed") == (index == 1)
    # An active-state check on a different variable must not stand in for this assignment.
    quest["implementation_notes"][3] = quest["implementation_notes"][3].replace("Check: quest_state == active", "Check: quest_active == true")
    assert "restart_reactivation" in {item["code"] for item in assess_artifact_quality(content, review_request=human_request)["request_coverage_gaps"]}


@pytest.mark.parametrize("state,check", [
    ("quest_state set to active and both flags reset", "quest_state == active OR guards_cleared == false"),
    ("never quest_state set to active", "quest_state == active"),
    ("quest_state set to inactive", "quest_state == active"),
])
def test_restart_does_not_accept_optional_negated_or_inactive_activation(state, check):
    content = frostpeak_dialogue_review(corrected=True)
    content["quest_hooks"]["content"]["quests"][0]["implementation_notes"][-1] = (
        f"Proposal - Restart: New attempt; Event: player restarts; State: {state}; Check: {check}")
    assert "restart_reactivation" in {item["code"] for item in assess_artifact_quality(content, review_request=FROST_REQUEST)["request_coverage_gaps"]}

POLICY = (
    "Link/file warnings once per object per mission attempt; firewall warnings once per barrier "
    "per mission attempt. Reset ONLY on mission restart, never on scanner/URL checks, quarantine or barrier crossing."
)


def test_generated_pairs_derive_hooks_but_ambiguous_saved_hooks_still_fail():
    assert "dialogue_hooks" not in NPCDesignCandidate.model_json_schema()["properties"]
    assert "manual_test" not in DialogueTriggerMapping.model_json_schema()["properties"]
    content = artifact()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc.pop("dialogue_hooks")
    original = copy.deepcopy(content)
    result = validate_generated_blueprint(content, EVIDENCE)
    assert result["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] == LINES
    assert content == original
    npc["dialogue_hooks"] = ["PATCH teaches core mechanics."]
    with pytest.raises(ValueError, match="do not exactly cover"):
        validate_generated_blueprint(content, EVIDENCE)


def test_human_policy_is_preserved_verbatim_and_fresh_reuse_cannot_be_confirmed_away():
    content = artifact()
    original = copy.deepcopy(content)
    result = validate_generated_blueprint(content, EVIDENCE, dialogue_policy=POLICY, fresh_dialogue=True)
    npc = result["npc_archetypes"]["content"]["npcs"][0]
    assert npc["fresh_dialogue"] is True
    for mapping in npc["dialogue_triggers"]:
        assert mapping["repeat_policy"] == POLICY
        assert POLICY in mapping["manual_test"]
        assert any(POLICY in note and mapping["text"] in note for note in npc["implementation_notes"])
    assert content == original
    score = assess_artifact_quality(result)
    assert "Fresh dialogue" in score["blockers"]
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
    assert "Fresh dialogue" in assess_artifact_quality(result, confirmations)["blockers"]
    # The API must enforce the same request even with the local/mock provider.
    db = MagicMock()
    run = SimpleNamespace(id=uuid4(), game_project_id="local-check", provider_name="mock",
                          status="awaiting_review", objective="Review fresh dialogue.", model_config={"fresh_dialogue": True})
    saved = SimpleNamespace(id=uuid4(), evidence_snapshot_id=uuid4(), content=result,
                            run_id=run.id, game_project_id=run.game_project_id, immutable=False, artifact_type="draft")
    from app.models.design_agent import DesignAgentArtifact, DesignAgentCritique, DesignAgentEvidenceSnapshot
    rows = {DesignAgentArtifact: saved, DesignAgentEvidenceSnapshot: SimpleNamespace(items=EVIDENCE),
            DesignAgentCritique: SimpleNamespace(content={"verdict": "ready_for_review", "findings": []}, provider_name="mock")}
    def query(model):
        query_result = MagicMock()
        query_result.filter.return_value = query_result.order_by.return_value = query_result
        query_result.first.return_value = rows.get(model)
        return query_result
    db.query.side_effect = query
    service = DesignAgentService()
    service._get_run = lambda db, run_id, project: run
    with pytest.raises(HTTPException) as rejected:
        service.review(db, run.id, "local-check", "approve", None, None, confirmed_proposals=confirmations,
                       artifact_id=saved.id)
    assert rejected.value.status_code == 409 and "Fresh dialogue" in rejected.value.detail
    db.commit.assert_not_called()
    assert "Fresh dialogue" not in assess_artifact_quality(validate_generated_blueprint(content, EVIDENCE))["blockers"]
    # A model-authored policy change on a later revision cannot replace run-level direction.
    npc["dialogue_triggers"][0]["repeat_policy"] = "Reset on scanner use."
    npc["dialogue_hooks"][0] = npc["dialogue_triggers"][0]["text"] = "No click yet, Adi. Let's inspect that address."
    revised = validate_generated_blueprint(result, EVIDENCE, dialogue_policy=POLICY, fresh_dialogue=True)
    assert all(pair["repeat_policy"] == POLICY for pair in revised["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"])


def test_run_input_is_bounded_and_prompts_request_complete_quest_transitions():
    values = {"objective": "Create a reviewed game design.", "document_ids": ["11111111-1111-1111-1111-111111111111"]}
    payload = DesignAgentRunCreate(**values, dialogue_policy=POLICY, fresh_dialogue=True)
    assert payload.dialogue_policy == POLICY and payload.fresh_dialogue
    for policy in [" ", "x" * 241]:
        with pytest.raises(ValidationError):
            DesignAgentRunCreate(**values, dialogue_policy=policy)
    for action in ["generate", "revise"]:
        content = BlueprintContent.model_validate(artifact()).model_dump()
        capture = BlueprintCapturingProvider(content)
        provider = NvidiaDesignAgentProvider(llm_provider=capture)
        if action == "generate":
            provider.generate({"objective": values["objective"], "dialogue_policy": POLICY, "fresh_dialogue": True}, EVIDENCE)
        else:
            evidence = [{**item, "matched_sections": ["quest_hooks"]} for item in EVIDENCE]
            provider.revise(content, evidence, "Improve quest integration.", ["quest_hooks"])
        assert len(capture.requests) == 1
        prompt = capture.requests[0].messages[1]["content"]
        assert "Completion requires ALL and ONLY these flags" in prompt
        assert "reevaluates after each_objective_update" in prompt
        assert "restart atomically clears ALL flags and sets active" in prompt
        assert "Separate lifecycle active/failed/completed from these flags" in prompt
        if action == "generate":
            assert "omit NPC dialogue_hooks" in prompt
            plan = json.loads(prompt.split("Input: ", 1)[1])["plan"]
            assert plan["dialogue_policy"] == POLICY and plan["fresh_dialogue"]

    # Exercise real workflow callbacks with an in-memory DB double: no schema reset.
    run = SimpleNamespace(id=uuid4(), game_project_id="local-check", objective=values["objective"],
                          document_ids=values["document_ids"], max_revisions=2, revision_count=0,
                          model_config={"dialogue_policy": POLICY, "fresh_dialogue": True})
    workflow = DesignAgentWorkflow.__new__(DesignAgentWorkflow)
    graph = MagicMock()
    graph.invoke.side_effect = lambda state, config: state
    workflow._checkpointer = lambda: nullcontext(None)
    workflow._compile = lambda saver: graph
    state = workflow.start(run)
    assert state["dialogue_policy"] == POLICY and state["fresh_dialogue"]
    state.update(plan={"objective": values["objective"]}, evidence_items=EVIDENCE,
                 evidence_snapshot_id=str(uuid4()))
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.flush.side_effect = lambda: setattr(db.add.call_args.args[0], "id", uuid4())
    capture = BlueprintCapturingProvider(BlueprintContent.model_validate(artifact()).model_dump())
    workflow.provider = NvidiaDesignAgentProvider(llm_provider=capture)
    workflow._provider_node = lambda state, node, call, persist: persist(db, run, call())
    generated = workflow._generate_blueprint(state)
    state.update(generated)
    npc = generated["current_artifact"]["npc_archetypes"]["content"]["npcs"][0]
    assert npc["fresh_dialogue"] and all(pair["repeat_policy"] == POLICY for pair in npc["dialogue_triggers"])
    changed = copy.deepcopy(generated["current_artifact"])
    changed_npc = changed["npc_archetypes"]["content"]["npcs"][0]
    changed_npc["dialogue_hooks"][0] = changed_npc["dialogue_triggers"][0]["text"] = "No click yet, Adi. Inspect that address."
    changed_npc["dialogue_triggers"][0]["repeat_policy"] = "Reset on scanner use."
    workflow.provider = NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(changed))
    state.update(rejection_reason="Improve the PATCH profile warning.", revision_targets=["npc_archetypes"])
    revised = workflow._revise(state)["current_artifact"]["npc_archetypes"]["content"]["npcs"][0]
    assert revised["fresh_dialogue"] and all(pair["repeat_policy"] == POLICY for pair in revised["dialogue_triggers"])
