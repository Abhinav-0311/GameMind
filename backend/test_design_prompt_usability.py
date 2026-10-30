"""Prompt-contract regressions; capture transport only, never hosted calls."""
import json
import copy
from pathlib import Path

import pytest

from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from app.design_agent.provider import MockDesignAgentProvider
from test_nvidia_design_agent_provider import BlueprintCapturingProvider
from test_quest_state_contract import typed_artifact


@pytest.mark.parametrize("fresh", [True, False])
def test_fresh_generation_separates_example_lines_without_rewriting_source(fresh):
    from test_revision_completeness_guards import complete_artifact

    source = (Path(__file__).resolve().parents[1] / "docs/demo/cyberrakshak_gdd.md").read_text(encoding="utf-8")
    start = source.index("## 10. PATCH companion system")
    end = source.index("## 11. Wrong interaction mechanic")
    passage = source[start:end]
    evidence = [{"chunk_id": "patch", "document_id": "cyber", "content": passage,
                 "matched_sections": ["npc_archetypes", "npc_memory_design"], "similarity": 0.9}]
    original = copy.deepcopy(evidence)
    capture = BlueprintCapturingProvider(typed_artifact())
    NvidiaDesignAgentProvider(llm_provider=capture).generate({"fresh_dialogue": fresh}, evidence)
    payload = json.loads(capture.requests[0].messages[1]["content"].split("Input: ", 1)[1])
    projected = payload["evidence"][0]
    assert evidence == original
    if not fresh:
        assert projected["content"] == passage
        assert "omitted_dialogue_examples" not in projected
        return
    assert "content" not in projected  # A filtered concatenation must not masquerade as a source excerpt.
    assert len(projected["omitted_dialogue_examples"]) == 5
    assert "That link is trying too hard" not in json.dumps(payload)
    assert "Gameplay role: provides hints, scans, warnings, and feedback." in json.dumps(payload)
    assert "Phase 1 uses fully scripted dialogue" in json.dumps(payload)
    ranges = [*projected["content_segments"], *projected["omitted_dialogue_examples"]]
    cursor = 0
    for span in sorted(ranges, key=lambda item: item["excerpt_start"]):
        assert span["excerpt_start"] == cursor
        cursor = span["excerpt_end"]
        if "content" in span:
            assert span["content"] == passage[span["excerpt_start"]:cursor]
    assert cursor == len(passage)


def test_example_projection_keeps_quoted_facts_and_absolute_source_offsets():
    passage = ('Mira guards the "North Gate".\r\nSample dialogue:\r\n'
               '- “Keep your shield up.”\r\n\r\n## Rules\r\n- "North Gate" is the destination.\r\n')
    evidence = [{"chunk_id": "mira", "content": passage, "excerpt_start": 80,
                 "excerpt_end": 80 + len(passage)}]
    original = copy.deepcopy(evidence)
    projected = NvidiaDesignAgentProvider._fresh_dialogue_evidence(evidence)[0]
    assert evidence == original
    assert len(projected["omitted_dialogue_examples"]) == 1
    kept = "".join(span["content"] for span in projected["content_segments"])
    assert 'Mira guards the "North Gate"' in kept and '"North Gate" is the destination' in kept
    assert "Keep your shield up" not in kept
    for span in projected["content_segments"]:
        assert span["content"] == passage[span["excerpt_start"] - 80:span["excerpt_end"] - 80]


@pytest.fixture(params=["generate", "revise"])
def design_prompt(request):
    evidence = [{"chunk_id": "mentor", "content": "Mira teaches gate authentication.",
                 "matched_sections": ["npc_archetypes", "quest_hooks"], "similarity": 0.9}]
    content = MockDesignAgentProvider().generate({"objective": "Build a reviewed design."}, evidence).content
    capture = BlueprintCapturingProvider(content)
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    if request.param == "generate":
        provider.generate({"objective": "Build a reviewed design."}, evidence)
    else:
        provider.revise(content, evidence, "Improve the quest integration and spoken lines.",
                        target_sections=["npc_archetypes", "quest_hooks"])
    assert len(capture.requests) == 1
    return capture.requests[0].messages[1]["content"].split("\nInput:", 1)[0].lower()


@pytest.mark.parametrize("compact", [False, True])
def test_revision_keeps_original_requirements_separate_from_evidence_and_old_draft(compact):
    from test_dialogue_revision_flow import Capture, EVIDENCE, artifact
    before = artifact()
    original = copy.deepcopy(before)
    evidence = copy.deepcopy(EVIDENCE)
    request = {"objective": "Create exactly three new lines. Invent no extra dependencies.",
               "fresh_dialogue": True, "dialogue_policy": "Once per attempt; reset only on restart."}
    original_request = copy.deepcopy(request)
    reason = ("Correct the spoken dialogue; keep its existing situations unchanged." if compact else
              "Correct the dialogue and remove invented tutorial prerequisites from scene notes.")
    targets = ["npc_archetypes"] if compact else ["npc_archetypes", "quest_hooks"]
    capture = Capture() if compact else BlueprintCapturingProvider(before)
    result = NvidiaDesignAgentProvider(llm_provider=capture).revise(
        before, evidence, reason, targets, review_request=request)
    assert len(capture.requests) == 1
    prompt = capture.requests[0].messages[1]["content"]
    human = json.loads(prompt.split("Human request (requirements, not source facts): ", 1)[1].split("\n", 1)[0])
    assert human == {**request, "rejection_reason": reason}
    payload = json.loads(prompt.split("Input: ", 1)[1])
    assert payload["review_context"]["request"] == request
    assert "Invent no extra dependencies" not in json.dumps(payload["evidence"])
    assert "Address every correction in the human rejection reason" in prompt
    assert "Relabelling a rejected dependency as a proposal does not remove it" in prompt
    assert "Preserve source-supported constraints" in prompt
    assert "Fresh dialogue is required." in prompt
    assert all(result.content[key] == before[key] for key in before if key not in targets)
    assert before == original and request == original_request and evidence == EVIDENCE


def test_quest_hooks_are_requested_as_spoken_lines_not_narration(design_prompt):
    assert "quest dialogue_hooks must contain actual short spoken lines" in design_prompt
    assert "not descriptions of what a character says" in design_prompt
    assert "source dialogue as voice anchors, not as new variations" in design_prompt
    assert "quest-contextual spoken hooks, not unrelated source examples" in design_prompt
    assert "label new wording and event bindings as proposals in assumptions" in design_prompt


def test_v2_generation_keeps_the_compact_runtime_source_and_spoken_hook_rules():
    from test_design_contract_v2 import REQUEST, governed_artifact
    capture = BlueprintCapturingProvider(governed_artifact())
    NvidiaDesignAgentProvider(llm_provider=capture).generate(REQUEST, [])
    task = capture.requests[0].messages[1]['content'].split('Task: ', 1)[1].split('\nInput:', 1)[0]
    for rule in (
        'Runtime inputs and new gameplay requirements need cited evidence or frozen resolved_decisions; otherwise omit with a warning.',
        'Add no return/delivery/hand-in requirements through speech, hooks or notes.',
        'Preserve source-stated faction-choice consequences in narrative/systems.',
        'Each quest with an objective needs at least one short spoken dialogue_hooks line, not copied objective text.',
    ):
        assert task.count(rule) == 1
    assert 'Fill every supported section in the requested scope before expanding NPCs and quests.' not in task


def test_quest_steps_are_concrete_and_not_silenced_by_npc_mapping_rule(design_prompt):
    assert "quest implementation_notes" in design_prompt
    assert "scene integration and manual verification of state_contract" in design_prompt
    assert "leave implementation_notes empty rather than duplicating the mappings" not in design_prompt
    assert "one observable player action with a completion condition" in design_prompt
    assert "every quest must have state_contract version 1" in design_prompt
    assert "one exact objective text, distinct boolean flag and observable event per objective" in design_prompt
    assert "omit duplicate objective/event/state/check notes" in design_prompt
    assert "proximity or animation is not success" in design_prompt
    assert "section content closes with }, not ]" in design_prompt
    assert "active-attempt restriction in the progress situation" in design_prompt
    assert "player's confirmation action, not only an event identifier" in design_prompt
    assert "quest_failed or player_confirmed_restart are identifiers, not action descriptions" in design_prompt
    assert "expected flags, lifecycle and dialogue eligibility" in design_prompt
    assert "not an ordering engine" in design_prompt
    assert "generic 'map objectives to events' instructions are not integration steps" in design_prompt


def test_generation_preserves_source_rewards_and_requested_completion_situation(design_prompt):
    assert "runtime null does not preserve a reward" in design_prompt
    assert "put explicit source rewards in quest.reward" in design_prompt
    assert "a completion line must acknowledge all required actions" in design_prompt
    assert "preserving all other progress" in design_prompt
    assert "both zero and partial objective completion" in design_prompt
    assert "partial-progress lines do not substitute for requested completion dialogue" in design_prompt


def test_shared_progress_guidance_for_generation_and_revision_covers_both_failure_directions(design_prompt):
    assert "never assert that every objective is still unfinished" in design_prompt
    assert "do not assert a particular objective is complete or incomplete" in design_prompt
    assert "use a state-neutral reminder" in design_prompt
    assert "all incomplete flag combinations" in design_prompt


def test_empty_typed_sections_match_the_actual_json_contract(design_prompt):
    assert 'npc_archetypes.content must be {"npcs":[]}' in design_prompt
    assert 'quest_hooks.content must be {"quests":[]}' in design_prompt


def test_dialogue_repeat_guidance_preserves_eligibility_and_named_resets(design_prompt):
    assert "first-interaction greeting must not also promise replay on every interaction" in design_prompt
    assert "name the permitted reset event, or explicitly state no reset" in design_prompt
    assert "a reset does not bypass situation eligibility" in design_prompt
    assert "quest state changes alone is not a named reset event" in design_prompt


def test_scene_guidance_distinguishes_source_constraints_and_proposed_bindings(design_prompt):
    assert "label scene placement and quest activation choices as integration proposals" in design_prompt
    assert "keep cited source constraints separate from proposed scene instructions" in design_prompt
    assert "record each proposal's scope in that npc or quest's assumptions" in design_prompt
    assert "do not claim an event fires or a quest activates as verified engine behavior" in design_prompt


def test_known_level_sequence_is_not_cut_by_per_record_limits(design_prompt):
    assert "preserve all source-defined level entries" in design_prompt
    assert "limit every list to three short items" not in design_prompt
    assert "no more than three short items in any list" not in design_prompt


def test_revision_requests_material_changes_in_every_selected_section():
    content = MockDesignAgentProvider().generate({"objective": "Build a design."}, []).content
    capture = BlueprintCapturingProvider(content)
    NvidiaDesignAgentProvider(llm_provider=capture).revise(
        content, [], "Correct both sections.", target_sections=["npc_archetypes", "quest_hooks"])
    prompt = capture.requests[0].messages[1]["content"].lower()
    assert "materially change every selected section" in prompt
    assert "typography and review metadata do not count" in prompt
    assert "a notes-only correction may remove rejected authored integration notes" in prompt
    assert "preserve every other field exactly" in prompt

    from test_dialogue_revision_flow import Capture, EVIDENCE, artifact

    capture = Capture()
    NvidiaDesignAgentProvider(llm_provider=capture).revise(
        artifact(), EVIDENCE, "Generate fresh dialogue.", target_sections=["npc_archetypes"])
    prompt = capture.requests[0].messages[1]["content"].lower()
    assert "source dialogue as voice anchors, not as new variations" in prompt
    assert "reuse appropriate quoted dialogue when available" not in prompt
    assert "label new wording and event bindings as proposals in assumptions" in prompt


def test_critique_checks_usefulness_and_not_merely_citation_presence():
    from app.design_agent.grounding import validate_generated_blueprint
    from app.design_agent.llm_provider import CompletionResult
    from test_dialogue_trigger_alignment import EVIDENCE, artifact

    class Capture:
        def complete(self, request):
            self.request = request
            return CompletionResult(content={"verdict": "needs_revision", "findings": [],
                                              "summary": "Needs review."},
                                    provider_name="nvidia", model_name="fixture")

    capture = Capture()
    content = validate_generated_blueprint(artifact(), EVIDENCE)
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    assert any("implementation proposals" in assumption for assumption in npc["assumptions"])
    request = {"objective": "Greeting, progress and completion after both required actions; preserve source rewards."}
    NvidiaDesignAgentProvider(llm_provider=capture).critique(content, EVIDENCE, review_request=request)
    prompt = capture.request.messages[1]["content"].lower()
    assert "citation presence is not proof of factual support" in prompt
    assert "spoken quest dialogue" in prompt
    assert "event-to-state integration steps" in prompt
    assert "empty design sections" in prompt
    assert "read assumptions, warnings and implementation_notes before judging a claim" in prompt
    assert "dialogue_triggers are proposed mappings, not active runtime bindings" in prompt
    assert "do not infer runtime approval or execution from structured fields or manual tests" in prompt
    assert "human confirmation pending is not itself a source contradiction" in prompt
    assert "new wording need not appear verbatim in the gdd" in prompt
    assert "still flag mismatched situation/line pairs" in prompt
    # The test exercises the normal critique boundary, not a different QA-only feature.
    payload = json.loads(capture.request.messages[1]["content"].split("Input: ", 1)[1])
    assert payload["artifact"]["quest_hooks"] == content["quest_hooks"]
    assert payload["artifact"]["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["text"] == npc["dialogue_triggers"][0]["text"]
    context = payload["review_context"]
    assert context["request"] == request
    assert "quest_check_conflicts" not in context
    assert context["stage"] == "unapproved_design_draft"
    assert "quest_integration_gaps" not in context
    assert "field presence alone does not prove usefulness" in prompt
    assert any(item["record_id"] == "PATCH" for item in context["pending_proposals"])
    assert "traceability only" in context["citation_scope"].lower()
    assert "absence from the gdd alone is not a defect" in prompt
    assert "do not recommend deleting valid proposals" in prompt
    assert "what the cited passage actually says" in prompt
    assert "read the complete cited objective passage" in prompt
    assert "check all four boolean states and both action orders" in prompt
    assert "runtime null is not reward preservation" in prompt
    assert "requested completion situation" in prompt


@pytest.mark.parametrize("note_retained", [False, True])
def test_critic_excludes_history_without_hiding_current_artifact_defects(note_retained):
    """Capture the real critique prompt, without claiming offline semantic acceptance."""
    from test_phase3_generation_contract import frostpeak_four_request_reference

    content = frostpeak_four_request_reference()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    rejected_note = "Scene integration proposal: Eldrin is accessible after initial tutorial."
    npc["implementation_notes"] = ["Manual verification: check first greeting and explicit restart."]
    if note_retained:
        npc["implementation_notes"].append(rejected_note)
    request = {"objective": "Preserve Eldrin's dialogue and the source quest reward.",
               "rejection_reason": f"Delete the entire implementation_notes entry: {rejected_note}",
               "fresh_dialogue": False, "dialogue_policy": "Once per attempt; reset on explicit restart.",
               "review_history": "Earlier draft failed; this is not current artifact content."}
    original, original_request = copy.deepcopy(content), copy.deepcopy(request)
    finding = {"severity": "high", "section": "npc_archetypes",
               "issue": f"Delete the rejected note: {rejected_note}",
               "recommendation": "Check the current NPC implementation_notes against the request."}
    capture = BlueprintCapturingProvider({"verdict": "needs_revision", "findings": [finding],
                                          "summary": "Review the current draft."})
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [], review_request=request)

    prompt = capture.requests[0].messages[1]["content"]
    payload = json.loads(prompt.split("Input: ", 1)[1])
    context = payload["review_context"]
    expected_request = {key: original_request[key] for key in ("objective", "fresh_dialogue", "dialogue_policy")}
    assert context["request"] == expected_request
    prefix = prompt.split("\nTask:", 1)[0]
    human_request = prefix.split("Human request (requirements, not source facts): ", 1)[1].strip()
    assert json.loads(human_request) == expected_request
    assert "rejection_reason" not in prompt and "review_history" not in prompt
    assert original_request["rejection_reason"] not in prompt
    assert original_request["review_history"] not in prompt
    assert context["review_basis"] == {
        "artifact": "Current draft; use it to establish what the draft currently contains.",
        "request": "Human requirements, not GDD evidence or proof of current defects.",
        "scope": "Current-artifact quality against evidence and original requirements; not compliance with historical revision requests.",
    }
    assert "For a current defect, identify its current field and exact value" in prompt
    assert "For a missing requirement, identify the current field or section where it is absent" in prompt
    current_notes = payload["artifact"]["npc_archetypes"]["content"]["npcs"][0]["implementation_notes"]
    assert (rejected_note in current_notes) is note_retained
    assert (rejected_note in prompt) is note_retained
    assert payload["artifact"] == NvidiaDesignAgentProvider._critic_artifact(original)
    # Even an apparently stale finding is retained: input guidance is not a verdict filter.
    assert result.content["findings"][0] == finding
    assert result.content["verdict"] == "needs_revision"
    assert content == original and request == original_request and len(capture.requests) == 1


def test_critic_projection_removes_only_exact_server_derived_duplicates():
    from app.design_agent.grounding import validate_generated_blueprint
    from test_dialogue_trigger_alignment import EVIDENCE, artifact
    content = validate_generated_blueprint(artifact(), EVIDENCE)
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    important_note = "Dialogue trigger proposal 'custom': retain this distinct design constraint."
    npc["implementation_notes"].append(important_note)
    original = copy.deepcopy(content)
    projected = NvidiaDesignAgentProvider._critic_artifact(content)
    compact = projected["npc_archetypes"]["content"]["npcs"][0]
    assert content == original and len(json.dumps(projected)) < len(json.dumps(content))
    assert "dialogue_hooks" not in compact
    assert all("manual_test" not in mapping for mapping in compact["dialogue_triggers"])
    assert important_note in compact["implementation_notes"]
    assert compact["assumptions"] == npc["assumptions"]
    assert projected["quest_hooks"] == content["quest_hooks"]
    from app.design_agent.finding_reviews import _artifact_value
    indexed = NvidiaDesignAgentProvider._critic_artifact(content, design_contract_version=2)
    note_path = f"/npc_archetypes/content/npcs/0/implementation_notes/{npc['implementation_notes'].index(important_note)}"
    assert _artifact_value(indexed, note_path) == _artifact_value(content, note_path) == important_note
    assert isinstance(indexed["npc_archetypes"]["content"]["npcs"][0]["implementation_notes"], dict)
    assert content == original
    # A non-derived manual test or mismatched hooks may reveal a defect: never hide them.
    npc["dialogue_triggers"][0]["manual_test"] = "Distinct design test."
    npc["dialogue_hooks"] = ["An unmatched line."]
    projected = NvidiaDesignAgentProvider._critic_artifact(content)
    compact = projected["npc_archetypes"]["content"]["npcs"][0]
    assert compact["dialogue_hooks"] == npc["dialogue_hooks"]
    assert compact["dialogue_triggers"][0]["manual_test"] == "Distinct design test."


@pytest.mark.parametrize("issue", [
    "Eldrin's quest dialogue implies he gives the quest; label this association as a proposal.",
    "Quest reward contradicts the source: the draft claims 9999 gold rather than 100 gold.",
])
def test_critic_receives_field_contracts_without_overruling_its_findings(issue):
    """Input/preservation regression, not a claim that a model judges either case correctly."""
    from test_phase3_generation_contract import frostpeak_four_request_reference
    content = frostpeak_four_request_reference()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    quest = content["quest_hooks"]["content"]["quests"][0]
    npc["assumptions"] = ["Eldrin's role as quest giver is not source-supported; any connection is a proposal requiring confirmation."]
    quest["assumptions"] = ["Eldrin is not the quest giver in source; any connection is proposed and requires human confirmation."]
    quest["runtime"] = None
    if "9999" in issue:
        quest["reward"] = "9999 gold"
    original = copy.deepcopy(content)
    finding = {"severity": "high", "section": "quest_hooks", "issue": issue,
               "recommendation": "Inspect the exact field against its source and assumptions."}
    capture = BlueprintCapturingProvider({"verdict": "needs_revision", "findings": [finding], "summary": "Review."})
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [])
    payload = json.loads(capture.requests[0].messages[1]["content"].split("Input: ", 1)[1])
    contracts = payload["review_context"]["field_contracts"]
    assert "not a quest-giver assignment" in contracts["quest_hooks.content.quests[].dialogue_hooks"]
    assert "not active runtime bindings" in contracts["npc_archetypes.content.npcs[].dialogue_triggers"]
    assert "one task remains" in contracts["npc_archetypes.content.npcs[].dialogue_triggers"]
    assert "both flags false" in contracts["npc_archetypes.content.npcs[].dialogue_triggers"]
    assert "not proof of factual support" in contracts["assumptions"]
    assert "still check" in contracts["source_claims"]
    assert "Unverified integration guidance, not active engine behavior" in contracts["implementation_notes"]
    assert "source constraints remain binding" in contracts["implementation_notes"]
    assert "Scene placement and activation need explicit proposal scope" in contracts["implementation_notes"]
    assert payload["artifact"]["quest_hooks"] == content["quest_hooks"]
    assert payload["artifact"]["npc_archetypes"]["content"]["npcs"][0]["assumptions"] == npc["assumptions"]
    assert result.content["findings"][0] == finding
    assert result.content["verdict"] == "needs_revision"
    assert len(capture.requests) == 1 and content == original


def test_human_request_is_prominent_and_unmodified_before_task_and_schema():
    from app.design_agent.llm_provider import CompletionResult
    from test_revision_completeness_guards import complete_artifact
    request = {"objective": "Greeting, quest-in-progress reminder, completion after BOTH actions. Invent no timers.",
               "fresh_dialogue": True, "dialogue_policy": None}
    capture = BlueprintCapturingProvider(typed_artifact())
    NvidiaDesignAgentProvider(llm_provider=capture).generate(request, [])
    prompt = capture.requests[0].messages[1]["content"]
    prefix = prompt.split("\nTask:", 1)[0]
    assert json.dumps(request) in prefix
    assert "Human request (requirements, not source facts):" in prefix
    class CriticCapture:
        def complete(self, item):
            self.item = item
            return CompletionResult(content={"verdict": "needs_revision", "findings": [], "summary": "Review."},
                                    provider_name="nvidia", model_name="fixture")
    critic = CriticCapture()
    NvidiaDesignAgentProvider(llm_provider=critic).critique(complete_artifact(), [], review_request=request)
    prompt = critic.item.messages[1]["content"]
    assert json.dumps(request) in prompt.split("\nTask:", 1)[0]
    assert "Idle lore is not requested quest-progress or completion dialogue" in prompt
    assert "A directly stated source reward does not need an additional verification statement" in prompt


def test_generation_guides_supported_sections_and_exposes_incomplete_drafts_without_retry():
    import copy
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from test_revision_completeness_guards import complete_artifact

    content = typed_artifact()
    for section in BLUEPRINT_SECTION_KEYS:
        if section not in {"npc_archetypes", "quest_hooks"}:
            content[section]["content"] = {}
    before = copy.deepcopy(content)
    capture = BlueprintCapturingProvider(content)
    result = NvidiaDesignAgentProvider(llm_provider=capture).generate({"objective": "Build a design."}, [])
    assert len(capture.requests) == 1  # No extra hosted request or automatic filler.
    assert result.content == before and content == before
    assert result.metadata["generation_complete"] is False
    assert len(result.metadata["incomplete_sections"]) == 7
    prompt = capture.requests[0].messages[1]["content"]
    payload = json.loads(prompt.split("Input: ", 1)[1])
    assert set(payload["section_content_guide"]) == set(BLUEPRINT_SECTION_KEYS)
    assert "Fill every supported section before expanding NPCs and quests" in prompt
    assert "Low retrieval similarity does not erase explicit facts" in prompt

    # Complete designs are identified; sparse, uncited gaps stay valid review drafts.
    capture = BlueprintCapturingProvider(typed_artifact())
    assert NvidiaDesignAgentProvider(llm_provider=capture).generate({}, []).metadata["generation_complete"]
    for section in content.values():
        section["citations"] = []
        section["warnings"] = ["Source detail unavailable; human input required."]
    result = NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(content)).generate({}, [])
    assert result.metadata["generation_complete"] is False


@pytest.mark.parametrize("topic,defective", [
    ("voice", False), ("voice", True),
    ("freshness", False), ("freshness", True),
    ("restart", False), ("restart", True),
])
def test_critic_compares_current_evidence_without_prejudging_or_hiding_findings(topic, defective):
    """Input/policy regressions only; mocked judges do not prove semantic accuracy."""
    artifact = typed_artifact()
    npc = artifact["npc_archetypes"]["content"]["npcs"][0]
    quest = artifact["quest_hooks"]["content"]["quests"][0]
    npc["dialogue_style"] = "formal, slow, ancient-lore references"
    source = "NPC Mira is a mentor. She speaks formally and slowly, referencing ancient lore."
    if topic == "voice" and defective:
        source = "NPC Mira is a mentor. She speaks abruptly and avoids ancient-lore references."
    if topic == "freshness":
        source = 'Mira says: "Both actions are done; the road remembers your courage."'
        quest["dialogue_hooks"] = [
            "Both actions are done; the road remembers your courage." if defective
            else "The banner rises over a quiet pass. Your deeds will outlast this winter."
        ]
    if topic == "restart" and defective:
        quest["state_contract"]["restart"]["event"] = "Show the quest menu without restarting the attempt"
    evidence = [{"chunk_id": npc["source_chunk_ids"][0], "content": source,
                 "matched_sections": ["npc_archetypes", "quest_hooks"], "similarity": 0.9}]
    request = {"objective": "Source-supported voice, fresh completion dialogue, explicit restart.",
               "fresh_dialogue": True, "dialogue_policy": None,
               "rejection_reason": "Historical correction must not leak to independent review."}
    original = copy.deepcopy((artifact, evidence, request))
    finding = {"severity": "medium", "section": "quest_hooks", "issue": "Retained critic finding.",
               "recommendation": "Check the current draft against its cited evidence."}
    capture = BlueprintCapturingProvider({"verdict": "needs_revision", "findings": [finding], "summary": "Review."})
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(artifact, evidence, review_request=request)
    prompt = capture.requests[0].messages[1]["content"]
    payload = json.loads(prompt.split("Input: ", 1)[1])
    contracts = payload["review_context"]["field_contracts"]
    if topic == "voice":
        assert "same named character passage" in contracts["npc_archetypes.content.npcs[].dialogue_style"]
        assert "unsupported or contradictory traits still require findings" in prompt
        assert "Compression alone is not an unsupported trait" in contracts["npc_archetypes.content.npcs[].dialogue_style"]
    elif topic == "freshness":
        assert "shared quest meaning is not copied wording" in contracts["spoken_dialogue_freshness"]
        assert "exact or near-verbatim source dialogue" in prompt
        assert "a future completion condition is not a current-state claim" in prompt
        assert "separately review unsupported world effects" in prompt
    else:
        assert "restart.lifecycle=active" in contracts["quest_hooks.content.quests[].state_contract.restart"]
        assert "an incompatible event meaning is still a defect" in prompt
        assert "player's confirmation action" in contracts["quest_hooks.content.quests[].state_contract.restart"]
    assert "Evidence comparison before each finding" in prompt
    assert payload["artifact"]["quest_hooks"] == artifact["quest_hooks"]
    assert payload["artifact"]["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"] == npc["dialogue_style"]
    assert payload["evidence"][0]["content"] == source
    assert "Historical correction must not leak" not in prompt
    assert result.content["findings"][0] == finding and result.content["verdict"] == "needs_revision"
    assert (artifact, evidence, request) == original and len(capture.requests) == 1
