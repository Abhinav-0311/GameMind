"""Offline content-first generation checks; not fresh NVIDIA acceptance."""
import copy
import json

import pytest
from pydantic import ValidationError

from app.design_agent.content_draft import ContentBlueprintDraft, assemble_content_draft
from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, GovernedBlueprintContent, grounded_response_model
from app.design_agent.grounding import assess_artifact_quality, validate_generated_blueprint
from test_design_contract_v2 import REQUEST, governed_artifact
from test_nvidia_design_agent_provider import content_draft_fixture


def test_explicit_source_quest_facts_cannot_be_reauthored_in_generation_or_revision():
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider
    original = governed_artifact()
    quest = original["quest_hooks"]["content"]["quests"][0]
    quest.update(objective="Clear the guards and raise the Northern flag", reward="100 gold")
    evidence = [{"chunk_id": "11111111-1111-1111-1111-111111111111", "document_id": "source",
                 "chunk_index": 0, "matched_sections": list(original),
                 "content": "Quest Hook 1: Objective: Clear the guards and raise the Northern flag Reward: 100 gold"}]
    for field, wrong in (("objective", "Clear the guards"), ("reward", "900 gold")):
        invalid = copy.deepcopy(original)
        invalid["quest_hooks"]["content"]["quests"][0][field] = wrong
        provider = NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(
            invalid, source_ids={evidence[0]["chunk_id"]: "S0"}))
        with pytest.raises(ValidationError):
            provider.generate(REQUEST, evidence)
        provider = NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(invalid))
        with pytest.raises(ValidationError):
            provider.revise(original, evidence, "Improve integration notes only", ["quest_hooks"], review_request=REQUEST)
    provider = NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(
        original, source_ids={evidence[0]["chunk_id"]: "S0"}))
    result = provider.generate(REQUEST, evidence)
    assert result.content["quest_hooks"]["content"]["quests"][0]["reward"] == "100 gold"
    assert result.metadata["source_quest_facts"][0]["objective"] == "Clear the guards and raise the Northern flag"
    assert result.metadata["source_quest_facts"][0]["source_chunk_ids"] == [evidence[0]["chunk_id"]]
    conflict = {**evidence[0], "chunk_id": "conflicting-source", "content": evidence[0]["content"].replace("100 gold", "900 gold")}
    with pytest.raises(ValueError, match="Conflicting explicit quest rewards"):
        provider.generate(REQUEST, [*evidence, conflict])
    assert quest["reward"] == "100 gold"
    # A mission inferred from a level is a proposal, not an immutable source quest.
    inferred = {**evidence[0], "content": "The UI might show Quest 1: later.\n## Story mode level plan\n### Level 1: Gate\nFocus: Cross the bridge"}
    assert provider._source_quest_facts([inferred]) == []
    # The existing table parser supports either column order.
    table = {**evidence[0], "content": "| Objective | Quest | Reward |\n|---|---|---|\n| Collect 5 crystals | Crystal hunt | 100 gold |"}
    assert provider._source_quest_facts([table]) == [{"objective": "Collect 5 crystals", "reward": "100 gold", "source_chunk_ids": [evidence[0]["chunk_id"]]}]


def test_assembly_preserves_authored_content_and_derives_only_bookkeeping():
    source = governed_artifact()
    draft = content_draft_fixture(source)
    original = copy.deepcopy(draft)
    result = assemble_content_draft(draft)
    assert draft == original
    assert GovernedBlueprintContent.model_validate(result).model_dump() == result
    for section in BLUEPRINT_SECTION_KEYS:
        assert result[section]["citations"] == source[section]["citations"]
    quest = result["quest_hooks"]["content"]["quests"][0]
    authored = draft["quest_hooks"]["content"]["quests"][0]
    for key in ("objective", "reward", "failure_states", "dependencies", "source_chunk_ids", "runtime"):
        assert quest[key] == authored[key]
    state = quest["state_contract"]
    flags = [item["flag"] for item in state["objectives"]]
    events = [item["event"] for item in state["objectives"]] + state["failure"]["events"] + [state["restart"]["event"]]
    assert len(events) == len(set(events)) and set(events) == set(state["event_actions"])
    assert state["completion"]["required_flags"] == state["restart"]["clear_flags"] == flags
    for index, objective in enumerate(state["objectives"]):
        assert state["event_actions"][objective["event"]] == authored["objectives"][index]["completion_action"]
    npc = result["npc_archetypes"]["content"]["npcs"][0]
    mapping = npc["dialogue_triggers"][0]
    assert mapping["eligibility"] == {"stage": "progress", "quest_id": quest["id"], "lifecycle": "active", "progress": "incomplete"}
    assert mapping["text"] == draft["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["text"]
    assert npc["dialogue_hooks"] == [mapping["text"]] and mapping["text"] in mapping["manual_test"]
    assert "unverified implementation proposals" in npc["assumptions"][-1]
    assert "unverified implementation proposals" in quest["assumptions"][-1]
    assert validate_generated_blueprint(result, design_contract_version=2)


def test_explicit_quest_indexes_keep_reordered_dialogue_attached_to_the_right_quest():
    draft = content_draft_fixture(governed_artifact())
    quests = draft["quest_hooks"]["content"]["quests"]
    quests.append(copy.deepcopy(quests[0]))
    quests[1].update(title="Second quest", objective="Inspect the gate",
                     objectives=[{"objective": "Inspect the gate", "completion_action": "Player inspects the gate"}])
    npcs = draft["npc_archetypes"]["content"]["npcs"]
    line = npcs[0]["dialogue_triggers"][0]
    npcs.append(copy.deepcopy(npcs[0]))
    npcs[1]["dialogue_triggers"] = [dict(line, stage="completion", quest_index=1),
                                    dict(line, stage="progress", quest_index=0),
                                    dict(line, stage="failed", quest_index=1)]
    result = assemble_content_draft(draft)
    mappings = result["npc_archetypes"]["content"]["npcs"][1]["dialogue_triggers"]
    assert [line["eligibility"]["quest_id"] for line in mappings] == ["quest_2", "quest_1", "quest_2"]
    assert [line["eligibility"]["lifecycle"] for line in mappings] == ["completed", "active", "failed"]
    assert len({line["trigger"] for npc in result["npc_archetypes"]["content"]["npcs"] for line in npc["dialogue_triggers"]}) == 4


@pytest.mark.parametrize("change", ["unknown_quest", "no_quest", "failed_without_failure", "boolean_index", "duplicate_objective"])
def test_invalid_authored_references_and_objectives_are_not_repaired(change):
    draft = content_draft_fixture(governed_artifact())
    line = draft["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    quest = draft["quest_hooks"]["content"]["quests"][0]
    if change == "unknown_quest":
        line["quest_index"] = 1
    elif change == "no_quest":
        line["quest_index"] = None
    elif change == "boolean_index":
        line["quest_index"] = False
    elif change == "failed_without_failure":
        line["stage"] = "failed"
        quest["failure_states"] = []
    else:
        quest["objectives"].append(copy.deepcopy(quest["objectives"][0]))
    original = copy.deepcopy(draft)
    with pytest.raises(ValidationError):
        assemble_content_draft(draft)
    assert draft == original


def test_absent_failure_restart_and_citations_are_not_invented():
    draft = content_draft_fixture(governed_artifact())
    quest = draft["quest_hooks"]["content"]["quests"][0]
    quest.update(failure_states=[], restart_action=None)
    draft["quest_hooks"]["citations"] = []
    line = draft["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    line.update(stage="greeting", quest_index=None)
    result = assemble_content_draft(draft)
    state = result["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert state["failure"] is None and state["restart"] is None
    assert result["quest_hooks"]["citations"] == []
    assert result["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["eligibility"] == {
        "stage": "greeting", "quest_id": None, "lifecycle": None, "progress": "any"}
    score = assess_artifact_quality(result, review_request=REQUEST)
    assert next(metric for metric in score["metrics"] if metric["key"] == "completeness")["value"] == 1.0
    assert score["quest_integration_gaps"] == []
    missing = copy.deepcopy(result)
    missing["quest_hooks"]["content"]["quests"][0]["state_contract"] = None
    legacy = assess_artifact_quality(missing)
    assert next(metric for metric in legacy["metrics"] if metric["key"] == "completeness")["value"] < 1.0


@pytest.mark.parametrize("rule,blocked", [
    ("Guards remain alive at the Ash Pass border post", True),
    ("Northern flag not raised", True),
    ("Less than 5 chunks of raw sky-iron ore mined", True),
    ("Player health reaches zero during the active attempt", False),
    ("Guards remain alive when the evacuation deadline expires", False),
    ("Northern flag not raised at the evacuation deadline", False),
])
def test_failure_requires_an_event_not_ordinary_unfinished_progress(rule, blocked):
    from app.design_agent.grounding import complete_design_critique, validate_design_approval

    draft = content_draft_fixture(governed_artifact())
    draft["quest_hooks"]["content"]["quests"][0]["failure_states"] = [rule]
    content = assemble_content_draft(draft)
    original = copy.deepcopy(content)
    ready = {"verdict": "ready_for_review", "summary": "No defects found.", "findings": []}
    for hidden_in_action in (False, True):
        candidate = copy.deepcopy(content)
        quest = candidate["quest_hooks"]["content"]["quests"][0]
        if hidden_in_action:
            quest["failure_states"] = ["The active attempt ends"]
        score = assess_artifact_quality(candidate, review_request=REQUEST)
        assert ("quest_failure_predicate" in {gap["code"] for gap in score["request_coverage_gaps"]}) is blocked
        reviewed = complete_design_critique(ready, candidate, review_request=REQUEST)
        assert any("unfinished progress" in finding["issue"] for finding in reviewed["findings"]) is blocked
        if blocked:
            assert reviewed["verdict"] == "needs_revision"
            confirmed = [{key: item[key] for key in ("section", "record_id", "assumption")}
                         for item in score["unresolved_assumptions"]]
            with pytest.raises(ValueError, match="Request coverage"):
                validate_design_approval(candidate, [], ready, confirmed, review_request=REQUEST)
    assert content == original and ready["findings"] == []


@pytest.mark.parametrize("situation,stage,quest_index,blocked", [
    ("greeting", "progress", 0, True),
    ("quest_offer", "progress", 0, True),
    ("greeting", "greeting", 0, False),
    ("greeting", "greeting", None, False),
    ("Reminder during active incomplete quest", "progress", 0, False),
    ("quest_offer", "other", None, False),
])
def test_dialogue_situation_does_not_silently_become_progress(situation, stage, quest_index, blocked):
    from app.design_agent.grounding import complete_design_critique, validate_design_approval

    draft = content_draft_fixture(governed_artifact())
    line = draft["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    line.update(situation=situation, stage=stage, quest_index=quest_index)
    original = copy.deepcopy(draft)
    content = assemble_content_draft(draft)
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    assert mapping["eligibility"]["stage"] == stage
    assert mapping["eligibility"]["quest_id"] == ("quest_1" if quest_index is not None else None)
    assert mapping["situation"] == situation and mapping["text"] == line["text"]
    score = assess_artifact_quality(content, review_request=REQUEST)
    assert ("dialogue_stage_situation" in {gap["code"] for gap in score["request_coverage_gaps"]}) is blocked
    ready = {"verdict": "ready_for_review", "summary": "No defects found.", "findings": []}
    reviewed = complete_design_critique(ready, content, review_request=REQUEST)
    assert any("declared situation" in finding["issue"] for finding in reviewed["findings"]) is blocked
    if blocked:
        confirmed = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in score["unresolved_assumptions"]]
        with pytest.raises(ValueError, match="Request coverage"):
            validate_design_approval(content, [], ready, confirmed, review_request=REQUEST)
    assert draft == original and ready["findings"] == []


def test_quantity_guard_still_detects_authored_objective_and_action_losses():
    draft = content_draft_fixture(governed_artifact())
    quest = draft["quest_hooks"]["content"]["quests"][0]
    quest.update(objective="Mine 5 chunks of ore", objectives=[{"objective": "Mine ore", "completion_action": "Player mines ore"}])
    for objective, action, blocked in (("Mine ore", "Player mines ore", True),
                                      ("Mine 5 chunks of ore", "Player mines ore", True),
                                      ("Mine 5 chunks of ore", "Player's total reaches 5 chunks of ore", False)):
        quest["objectives"] = [{"objective": objective, "completion_action": action}]
        gaps = assess_artifact_quality(assemble_content_draft(draft), review_request=REQUEST)["request_coverage_gaps"]
        assert ("quest_quantity_coverage" in {gap["code"] for gap in gaps}) is blocked
    # Source quantity must survive even when all generated objective fields drop it.
    quest.update(title="Ore contract", objective="Mine ore", objectives=[{
        "objective": "Mine ore", "completion_action": "Player mines ore"}])
    source = {"chunk_id": quest["source_chunk_ids"][0], "matched_sections": ["quest_hooks"],
              "content": "| Quest | Objective | Reward |\n|---|---|---|\n| Ore contract | Mine 5 chunks of ore | |"}
    before = copy.deepcopy(draft)
    for event, blocked in (("Player mines ore", True), ("Player's total reaches 5 chunks of ore", False)):
        quest["objective"] = "Mine 5 chunks of ore" if not blocked else "Mine ore"
        quest["objectives"] = [{"objective": quest["objective"], "completion_action": event}]
        content = assemble_content_draft(draft)
        gaps = assess_artifact_quality(content, review_request=REQUEST, evidence=[source])["request_coverage_gaps"]
        assert ("quest_source_quantity_coverage" in {gap["code"] for gap in gaps}) is blocked
        assert not any(gap["code"] == "quest_source_quantity_coverage" for gap in
                       assess_artifact_quality(content, review_request=REQUEST, evidence=[{**source, "chunk_id": "foreign"}])["request_coverage_gaps"])
    assert before["quest_hooks"]["content"]["quests"][0]["objectives"][0]["completion_action"] == "Player mines ore"


def test_wire_schema_excludes_bookkeeping_but_keeps_grounding_and_runtime_boundaries():
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider

    draft = content_draft_fixture(governed_artifact())
    capture = BlueprintCapturingProvider(governed_artifact())
    NvidiaDesignAgentProvider(llm_provider=capture).generate(REQUEST, [])
    prompt = capture.requests[0].messages[1]["content"]
    assert "At most three spoken mappings per NPC" in prompt
    assert "no unsolicited greeting" in prompt
    assert "Add no return/delivery/hand-in requirements through speech, hooks or notes" in prompt
    assert "Runtime inputs and new gameplay requirements need cited evidence or frozen resolved_decisions" in prompt
    payload = json.loads(prompt.split("Input: ", 1)[1])
    assert payload["section_citation_ids"] == {section: [] for section in BLUEPRINT_SECTION_KEYS}
    overflow = copy.deepcopy(draft)
    mappings = overflow["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]
    mappings.extend([copy.deepcopy(mappings[0])] * (4 - len(mappings)))
    with pytest.raises(ValidationError):
        ContentBlueprintDraft.model_validate(overflow)
    schema = ContentBlueprintDraft.model_json_schema()
    assert "propertyNames" not in json.dumps(schema)
    assert not {"id", "state_contract"} & schema["$defs"]["DraftQuest"]["properties"].keys()
    assert not {"trigger", "eligibility", "manual_test"} & schema["$defs"]["DraftDialogue"]["properties"].keys()
    dialogue = schema["$defs"]["DraftDialogue"]
    for stage in ("greeting", "progress", "completion", "failed", "other"):
        for quest_index in (None, 0, 1):
            guided = any(stage in branch["properties"]["stage"]["enum"]
                         and ((quest_index is None) == (branch["properties"]["quest_index"]["type"] == "null"))
                         for branch in dialogue["anyOf"])
            assert guided == (quest_index is not None or stage in {"greeting", "other"})
    assert all(branch["required"] == dialogue["required"] for branch in dialogue["anyOf"])
    assert all(set(branch["properties"]) == set(dialogue["required"]) for branch in dialogue["anyOf"])
    source_id = draft["quest_hooks"]["citations"][0]
    evidence = [{"chunk_id": source_id, "matched_sections": list(BLUEPRINT_SECTION_KEYS),
                 "content": "Mira guards the pass and advises the player."}]
    supplied = [*evidence,
        {"chunk_id": "summary-only", "content": "The player guards the pass.", "matched_sections": ["summary"]},
        {"chunk_id": "npc-only", "content": "Mira advises the player.", "matched_sections": ["npc_archetypes"]}]
    original_evidence = copy.deepcopy(supplied)
    capture = BlueprintCapturingProvider(governed_artifact(), source_ids={source_id: "S0"})
    result = NvidiaDesignAgentProvider(llm_provider=capture).generate(REQUEST, supplied)
    scoped = json.loads(capture.requests[0].messages[1]["content"].split("Input: ", 1)[1])["section_citation_ids"]
    assert set(scoped["summary"]) == {"S0", "S1"}
    assert set(scoped["npc_archetypes"]) == {"S0", "S2"}
    assert all(scoped[key] == ["S0"] for key in BLUEPRINT_SECTION_KEYS if key not in {"summary", "npc_archetypes"})
    assert supplied == original_evidence
    assert all(section["citations"] == [source_id] for section in result.content.values())
    assert result.content["npc_archetypes"]["content"]["npcs"][0]["source_chunk_ids"] == [source_id]
    assert result.content["quest_hooks"]["content"]["quests"][0]["source_chunk_ids"] == [source_id]
    for invalid_reference in ("S2", "S99", source_id):
        with pytest.raises(ValidationError):
            NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(
                governed_artifact(), source_ids={source_id: invalid_reference})).generate(REQUEST, supplied)
    model = grounded_response_model(ContentBlueprintDraft, evidence, defer_runtime=True)
    draft["unity_runtime_preview"].update(content={}, citations=[], confidence="Low")
    assert model.model_validate(draft)
    for section, field in (("quest_hooks", "citations"), ("npc_archetypes", "source_chunk_ids")):
        invalid = copy.deepcopy(draft)
        target = invalid[section] if field == "citations" else invalid[section]["content"]["npcs"][0]
        target[field] = ["unknown-source"]
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
    invalid = copy.deepcopy(draft)
    invalid["quest_hooks"]["content"]["quests"][0]["runtime"] = {"npc_slug": "invented"}
    with pytest.raises(ValidationError):
        model.model_validate(invalid)


def test_syntax_recovery_retains_content_first_contract_without_semantic_repair():
    from test_json_closer_recovery import invoke
    draft = content_draft_fixture(governed_artifact())
    result, calls = invoke(json.dumps(draft)[:-1], model=ContentBlueprintDraft)
    assert len(calls) == 1 and result.metadata["local_recovery"]
    assert result.metadata["recovery_requires_review"] and result.metadata["repair_attempts"] == 0
    assert assemble_content_draft(result.content) == assemble_content_draft(draft)


@pytest.mark.parametrize("fault", ["unknown_reference", "duplicate_objective"])
def test_invalid_generation_stops_without_repair_and_preserves_usage_diagnostics(fault):
    import httpx
    from app.design_agent.llm_provider import NvidiaProvider, NvidiaStructuredOutputError
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from test_design_agent_llm_provider import _completion

    draft = content_draft_fixture(governed_artifact())
    if fault == "unknown_reference":
        draft["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["quest_index"] = 1
    else:
        objectives = draft["quest_hooks"]["content"]["quests"][0]["objectives"]
        objectives.append(copy.deepcopy(objectives[0]))
    calls = []
    def respond(request):
        calls.append(request)
        return _completion(json.dumps(draft), input_tokens=123, output_tokens=45)
    transport = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=True,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond)))
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        NvidiaDesignAgentProvider(llm_provider=transport).generate(REQUEST, [])
    assert len(calls) == 1
    diagnostics = caught.value.diagnostics
    assert sum(item["input_tokens"] for item in diagnostics["completions"]) == 123
    assert sum(item["output_tokens"] for item in diagnostics["completions"]) == 45
    assert diagnostics.get("assembly_failed") if fault == "duplicate_objective" else diagnostics["repair_skipped"] == "governed_schema_failure"
    assert "Player" not in str(caught.value) and "offline-only" not in str(caught.value)


def test_initial_generation_requires_concrete_section_fields_and_explicit_reward():
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider
    premise = "The game is a tactical adventure about restoring a frozen kingdom."
    capture = BlueprintCapturingProvider(governed_artifact(), source_ids={"11111111-1111-1111-1111-111111111111": "S0"})
    generated = NvidiaDesignAgentProvider(llm_provider=capture).generate(REQUEST, [{
        "chunk_id": "art-source", "document_id": "one-source", "chunk_index": 1,
        "title": "Example GDD", "content": "## Art Style\nThe visual identity of the game uses hand-painted textures and icy colors.",
        "matched_sections": list(governed_artifact()),
    }, {
        "chunk_id": "11111111-1111-1111-1111-111111111111", "document_id": "one-source", "chunk_index": 0,
        "title": "Example GDD", "content": "## Overview\n" + premise, "matched_sections": list(governed_artifact()),
    }])
    assert generated.content["summary"]["content"]["description"] == premise
    assert generated.content["summary"]["citations"] == ["11111111-1111-1111-1111-111111111111"]
    assert generated.metadata["locally_extracted_sections"] == ["summary"]
    assert "summary" not in capture.requests[0].response_model.model_json_schema()["properties"]
    capture = BlueprintCapturingProvider(governed_artifact(), source_ids={"11111111-1111-1111-1111-111111111111": "S0"})
    art_only = [{"chunk_id": "11111111-1111-1111-1111-111111111111", "document_id": "one-source",
                 "chunk_index": 0, "title": "Example GDD",
                 "content": "## Art Style\nThe game uses hand-painted textures and icy colors.",
                 "matched_sections": list(governed_artifact())}]
    generated = NvidiaDesignAgentProvider(llm_provider=capture).generate(REQUEST, art_only)
    assert generated.metadata["locally_extracted_sections"] == []
    assert generated.content["summary"] == governed_artifact()["summary"]
    assert "summary" in capture.requests[0].response_model.model_json_schema()["properties"]
    draft = content_draft_fixture(governed_artifact())
    before = copy.deepcopy(draft)
    for section in ("summary", "narrative_direction", "art_style_direction", "npc_memory_design", "level_design_suggestions", "gameplay_systems"):
        invalid = copy.deepcopy(draft)
        invalid[section].pop("content")
        with pytest.raises(ValidationError):
            ContentBlueprintDraft.model_validate(invalid)
        invalid[section]["content"] = {"description": "Unstructured replacement"} if section != "summary" else {}
        with pytest.raises(ValidationError):
            ContentBlueprintDraft.model_validate(invalid)
    missing = copy.deepcopy(draft)
    missing["quest_hooks"]["content"]["quests"][0].pop("reward")
    with pytest.raises(ValidationError):
        ContentBlueprintDraft.model_validate(missing)
    assert ContentBlueprintDraft.model_validate(draft)  # Explicit null reward remains valid when source lacks it.
    assert draft == before
    assert "propertyNames" not in json.dumps(ContentBlueprintDraft.model_json_schema())
    empty = copy.deepcopy(draft)
    empty["summary"]["content"] = {"description": None}
    empty["narrative_direction"]["content"] = {"lore_background": None, "themes": []}
    empty["art_style_direction"]["content"] = {"visual_theme": None, "visual_notes": []}
    empty["npc_memory_design"]["content"] = {"rules": []}
    empty["level_design_suggestions"]["content"] = {"levels": []}
    empty["gameplay_systems"]["content"] = {"systems": []}
    missing = assess_artifact_quality(assemble_content_draft(empty), review_request=REQUEST)["incomplete_sections"]
    assert len(missing) == 6  # Typed empty fields do not become invented facts or a completeness pass.


@pytest.mark.parametrize("reward", [None, "100 gold", "250 gold and 100 XP"])
def test_cited_source_reward_omission_or_change_blocks_even_a_clean_model_critique(reward):
    from app.design_agent.grounding import complete_design_critique, validate_design_approval
    content = governed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest["reward"] = reward
    evidence = [{"chunk_id": quest["source_chunk_ids"][0], "matched_sections": ["quest_hooks"],
                 "content": "- **Quest Hook 1**: Objective: Training Sandbox. Reward: 100 gold and 250 XP."}]
    before = copy.deepcopy(content)
    raw = {"verdict": "ready_for_review", "findings": [], "summary": "No defects found."}
    score = assess_artifact_quality(content, review_request=REQUEST, evidence=evidence)
    assert "quest_reward_coverage" in {gap["code"] for gap in score["request_coverage_gaps"]}
    confirmations = [{key: proposal[key] for key in ("section", "record_id", "assumption")} for proposal in score["unresolved_assumptions"]]
    assert "quest_reward_coverage" in {gap["code"] for gap in assess_artifact_quality(content, confirmations, review_request=REQUEST, evidence=evidence)["request_coverage_gaps"]}
    reviewed = complete_design_critique(raw, content, review_request=REQUEST, evidence=evidence)
    assert reviewed["verdict"] == "needs_revision" and any("source reward" in item["issue"] for item in reviewed["findings"])
    with pytest.raises(ValueError, match="Request coverage"):
        validate_design_approval(content, evidence, raw, confirmations, review_request=REQUEST)
    assert content == before and raw["findings"] == []


def test_reward_check_preserves_scoping_and_does_not_invent_unstated_rewards():
    content = governed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    source = {"chunk_id": quest["source_chunk_ids"][0], "matched_sections": ["quest_hooks"],
              "content": "| Quest | Objective | Reward |\n|---|---|---|\n| Training Sandbox | Clear guards and raise the flag | 100 gold and 250 XP |"}
    for text, reward in ((source["content"], "100 gold and 250 XP"),
                         ("Quest Hook 1: Objective: Unrelated mission. Reward: 900 gold.", None),
                         ("Quest Hook 1: Objective: Training Sandbox.", None)):
        quest["reward"] = reward
        assert not any(gap["code"].startswith("quest_reward") for gap in assess_artifact_quality(content, review_request=REQUEST, evidence=[{**source, "content": text}])["request_coverage_gaps"])
    quest["reward"] = None
    assert "quest_reward_coverage" in {gap["code"] for gap in assess_artifact_quality(content, review_request=REQUEST, evidence=[source])["request_coverage_gaps"]}
    assert not assess_artifact_quality(content, evidence=[source])["request_coverage_gaps"]  # Legacy policy stays unchanged.
    for foreign in ({**source, "chunk_id": "uncited"}, {**source, "matched_sections": ["summary"]}):
        assert not any(gap["code"].startswith("quest_reward") for gap in assess_artifact_quality(content, review_request=REQUEST, evidence=[foreign])["request_coverage_gaps"])
    quest["source_chunk_ids"].append("conflicting-source")
    conflict = {**source, "chunk_id": "conflicting-source", "content": source["content"].replace("100 gold and 250 XP", "900 gold")}
    assert "quest_reward_conflict" in {gap["code"] for gap in assess_artifact_quality(content, review_request=REQUEST, evidence=[source, conflict])["request_coverage_gaps"]}


def test_approval_numeric_guard_checks_action_facts_not_server_generated_keys():
    draft = content_draft_fixture(governed_artifact())
    draft["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["repeat_policy"] = "Once per mission attempt; reset only on confirmed mission restart."
    content = assemble_content_draft(draft)
    quest = content["quest_hooks"]["content"]["quests"][0]
    evidence = [{"chunk_id": quest["source_chunk_ids"][0], "matched_sections": list(BLUEPRINT_SECTION_KEYS),
                 "content": "Mira guides the player. Clear the guards and raise the Northern flag. The player dies during the attempt. The player confirms a new attempt."}]
    assert validate_generated_blueprint(content, evidence, require_actionable=True, design_contract_version=2)
    state = quest["state_contract"]
    event = state["objectives"][0]["event"]
    state["event_actions"][event] = "Defeat 99 guards at the pass"
    with pytest.raises(ValueError, match="unsupported numeric detail.*99"):
        validate_generated_blueprint(content, evidence, require_actionable=True, design_contract_version=2)
