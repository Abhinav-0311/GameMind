"""Content-first scoped revisions: offline contracts, not hosted quality proof."""
import copy
import json

import pytest

from app.design_agent.content_draft import (
    assemble_content_revision, content_revision_model, project_content_revision,
)
from app.design_agent.contracts import GovernedBlueprintContent, grounded_response_model
from app.design_agent.grounding import validate_generated_blueprint
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from test_design_contract_v2 import REQUEST, governed_artifact
from test_nvidia_design_agent_provider import BlueprintCapturingProvider


def source():
    return validate_generated_blueprint(governed_artifact(), design_contract_version=2)


def test_revision_wire_omits_bookkeeping_and_preserves_authored_guidance():
    original = source()
    original["npc_archetypes"]["content"]["npcs"][0]["fresh_dialogue"] = True
    quest = original["quest_hooks"]["content"]["quests"][0]
    quest["implementation_notes"].append("Scene integration proposal: bind interactions through the level controller.")
    before = copy.deepcopy(original)
    targets = ["npc_archetypes", "quest_hooks", "summary", "narrative_direction",
               "art_style_direction", "npc_memory_design", "level_design_suggestions", "gameplay_systems"]
    projected = project_content_revision(original, targets)
    schema = json.dumps(content_revision_model(targets, original).model_json_schema())
    assert set(projected) == set(targets)
    assert '"state_contract"' not in schema and '"eligibility"' not in schema and '"manual_test"' not in schema
    assert '"fresh_dialogue"' not in json.dumps(projected)
    assert '"completion_action"' in schema and '"quest_index"' in schema
    assert "Contract check (not executed)" not in json.dumps(projected)
    assert quest["implementation_notes"][-1] in json.dumps(projected)
    wire_quest = projected["quest_hooks"]["content"]["quests"][0]
    assert wire_quest["id"] == quest["id"] and "state_contract" not in wire_quest
    rebuilt = assemble_content_revision(original, projected)
    assert rebuilt["npc_archetypes"]["content"]["npcs"][0]["fresh_dialogue"] is True
    assert rebuilt["quest_hooks"]["content"]["quests"][0]["state_contract"] == quest["state_contract"]
    from pydantic import ValidationError
    from app.design_agent.content_draft import ContentBlueprintDraft
    for target in targets[2:]:
        model = content_revision_model([target], original)
        expected = ContentBlueprintDraft.model_fields[target].annotation.model_fields["content"].annotation
        assert model.model_fields[target].annotation.model_fields["content"].annotation is expected
        model.model_validate({target: projected[target]})
        malformed = copy.deepcopy(projected[target])
        malformed["content"] = {"review_note": "Done; source content omitted"}
        with pytest.raises(ValidationError):
            model.model_validate({target: malformed})
    assert original == before


def test_reordered_revision_preserves_quest_ids_objective_keys_and_dialogue_references():
    original = source()
    quests = original["quest_hooks"]["content"]["quests"]
    second = copy.deepcopy(quests[0])
    second.update(id="ore-contract", title="Ore contract")
    quests.append(second)
    targets = ["npc_archetypes", "quest_hooks"]
    wire = project_content_revision(original, targets)
    wire["quest_hooks"]["content"]["quests"].reverse()
    wire["quest_hooks"]["content"]["quests"][1]["objectives"].reverse()
    line = wire["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    line.update(stage="completion", quest_index=0, situation="After the ore contract completes", text="Your work is complete.")
    result = assemble_content_revision(original, wire)
    revised = result["quest_hooks"]["content"]["quests"]
    assert [q["id"] for q in revised] == ["ore-contract", quests[0]["id"]]
    assert revised[1]["state_contract"]["objectives"] == list(reversed(quests[0]["state_contract"]["objectives"]))
    mapping = result["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    assert mapping["trigger"] == original["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["trigger"]
    assert mapping["eligibility"] == {"stage": "completion", "quest_id": "ore-contract", "lifecycle": "completed", "progress": "complete"}
    assert set(result) == set(targets)


def test_npc_only_revision_keeps_quests_exact_and_uses_frozen_quest_context():
    from pydantic import ValidationError
    original = source()
    import httpx
    from app.design_agent.llm_provider import NvidiaProvider
    from test_design_agent_llm_provider import _completion
    wire_quest = project_content_revision(original, ["quest_hooks"])
    action = "Clear all guards at the border post"
    wire_quest["quest_hooks"]["content"]["quests"][0]["objectives"][0]["completion_action"] = action
    calls = []
    def section_response(request):
        from test_nvidia_design_agent_provider import field_revision_fixture
        calls.append(json.loads(request.content))
        return _completion(json.dumps(field_revision_fixture(project_content_revision(original, ["quest_hooks"]), wire_quest)))
    transport = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=False,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(section_response)))
    corrected = NvidiaDesignAgentProvider(llm_provider=transport).revise(
        original, [], "Correct only the guard completion action", ["quest_hooks"], review_request=REQUEST)
    old_state = original["quest_hooks"]["content"]["quests"][0]["state_contract"]
    new_state = corrected.content["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert new_state["event_actions"][old_state["objectives"][0]["event"]] == action
    assert new_state["objectives"] == old_state["objectives"]
    assert all(corrected.content[key] == original[key] for key in original if key != "quest_hooks")
    assert len(calls) == 1
    wire_quest = project_content_revision(original, ["quest_hooks"])
    wire_quest["quest_hooks"]["content"]["quests"][0]["objectives"][0]["objective"] = "Clear all guards from the pass"
    reworded = NvidiaDesignAgentProvider(llm_provider=transport).revise(
        original, [], "Clarify only the objective wording, preserving the action", ["quest_hooks"], review_request=REQUEST)
    reworded_state = reworded.content["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert reworded_state["objectives"][0]["flag"] == old_state["objectives"][0]["flag"]
    assert reworded_state["objectives"][0]["event"] == old_state["objectives"][0]["event"]
    assert reworded_state["completion"] == old_state["completion"]
    assert reworded_state["restart"] == old_state["restart"]
    assert reworded_state["event_actions"] == old_state["event_actions"]
    revised = copy.deepcopy(original)
    npc = revised["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_triggers"][0]["text"] = "There is still work to do at the pass."
    capture = BlueprintCapturingProvider(revised)
    result = NvidiaDesignAgentProvider(llm_provider=capture).revise(
        original, [], "Improve the progress line.", target_sections=["npc_archetypes"], review_request=REQUEST)
    request = capture.requests[0]
    payload = json.loads(request.messages[1]["content"].split("Input: ", 1)[1])
    assert result.metadata["revision_contract"] == "content_field_v2"
    assert set(request.response_model.model_fields) == {"changes"}
    assert result.content["quest_hooks"] == original["quest_hooks"]
    assert result.content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["text"] == npc["dialogue_triggers"][0]["text"]
    assert payload["quest_state_context"][0]["id"] == original["quest_hooks"]["content"]["quests"][0]["id"]
    assert "Contract check (not executed)" not in json.dumps(payload)
    assert len(capture.requests) == 1

    from test_dialogue_revision_flow import Capture
    from app.design_agent.content_draft import ContentBlueprintRevision
    before = copy.deepcopy(original)
    old_npc = original["npc_archetypes"]["content"]["npcs"][0]
    evidence = [{"chunk_id": identity, "content": f"{old_npc['name']} advises the player at the pass.",
                 "matched_sections": ["npc_archetypes"]} for identity in old_npc["source_chunk_ids"]]
    patch = {"npc_archetypes": {"patches": [{"name": old_npc["name"],
        "source_chunk_ids": old_npc["source_chunk_ids"], "assumptions": [],
        "dialogue_triggers": [{**{key: item[key] for key in ("trigger", "situation", "text", "repeat_policy")},
                               "text": "There is still work to do at the pass."}
                              for item in old_npc["dialogue_triggers"][:1]]}]}}
    focused = Capture(patch)
    corrected = NvidiaDesignAgentProvider(llm_provider=focused).revise(
        original, evidence, "Fix the shared progress dialogue so it fits zero and partial completion.",
        ["npc_archetypes"], review_request=REQUEST)
    assert corrected.metadata["revision_contract"] == "npc_dialogue_patch"
    wire = focused.requests[0]
    assert issubclass(wire.response_model, ContentBlueprintRevision)
    assert "Return a small dialogue patch" in wire.messages[1]["content"]
    assert "Generate the complete structured design draft" not in wire.messages[1]["content"]
    assert "state_contract v1 requires all flags" not in wire.messages[1]["content"]
    inputs = json.loads(wire.messages[1]["content"].split("Input: ", 1)[1])
    assert inputs["quest_state_context"][0]["state_contract"] == original["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert corrected.content["quest_hooks"] == original["quest_hooks"]
    assert corrected.content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["eligibility"] == old_npc["dialogue_triggers"][0]["eligibility"]
    assert original == before

    unrequested = copy.deepcopy(patch)
    unrequested["npc_archetypes"]["patches"][0]["assumptions"] = ["No persistent memory across attempts."]
    with pytest.raises(ValidationError):
        NvidiaDesignAgentProvider(llm_provider=Capture(unrequested)).revise(
            original, evidence, "Fix the progress dialogue.", ["npc_archetypes"], review_request=REQUEST)

    import httpx
    from app.design_agent.llm_provider import NvidiaProvider, NvidiaStructuredOutputError
    from test_design_agent_llm_provider import _completion
    invalid = copy.deepcopy(patch)
    invalid["npc_archetypes"]["patches"][0]["dialogue_triggers"] = []
    calls = []
    def respond(request):
        calls.append(request)
        return _completion(json.dumps(invalid))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = NvidiaDesignAgentProvider(llm_provider=NvidiaProvider(base_url="https://example.invalid/v1",
            timeout_seconds=1, repair_enabled=True, key_reader=lambda _: "offline-only", client=client))
        from app.design_agent.llm_provider import NvidiaConfigurationError
        for unusable in (
            [{key: value for key, value in item.items() if key != "matched_sections"} for item in evidence],
            [{**item, "matched_sections": ["summary"]} for item in evidence],
            [{**item, "content": ""} for item in evidence],
        ):
            with pytest.raises(NvidiaConfigurationError) as missing:
                provider.revise(original, unusable, "Fix the progress dialogue.", ["npc_archetypes"], review_request=REQUEST)
            assert missing.value.code == "evidence_payload_incomplete" and missing.value.attempts == 0
            assert not calls and original == before
        with pytest.raises(NvidiaStructuredOutputError) as caught:
            provider.revise(original, evidence, "Fix the progress dialogue.", ["npc_archetypes"], review_request=REQUEST)
    assert len(calls) == 1 and caught.value.diagnostics["repair_skipped"] == "governed_schema_failure"


def test_mixed_dialogue_revision_can_replace_assumptions_and_eligibility():
    original = source()
    revised = copy.deepcopy(original)
    npc = revised["npc_archetypes"]["content"]["npcs"][0]
    npc["assumptions"] = ["Speaker association with the border post quest is an unverified proposal."]
    line = npc["dialogue_triggers"][0]
    line.update(text="The pass is reclaimed.", situation="After both border post objectives complete.")
    line["eligibility"].update(stage="completion", lifecycle="completed", progress="complete")
    evidence = [{"chunk_id": identity, "content": f"{npc['name']} advises the player at the pass.",
                 "matched_sections": ["npc_archetypes"]} for identity in npc["source_chunk_ids"]]
    capture = BlueprintCapturingProvider(revised)
    result = NvidiaDesignAgentProvider(llm_provider=capture).revise(
        original, evidence, "Correct the spoken dialogue, replace its assumptions and correct completion eligibility.",
        ["npc_archetypes"], review_request=REQUEST)
    actual = result.content["npc_archetypes"]["content"]["npcs"][0]
    assert actual["assumptions"][0] == npc["assumptions"][0]
    assert actual["dialogue_triggers"][0]["eligibility"] == line["eligibility"]
    assert actual["dialogue_triggers"][0]["text"] == "The pass is reclaimed."
    assert all(result.content[key] == original[key] for key in original if key != "npc_archetypes")
    assert original == source()


@pytest.mark.parametrize("fault", ["foreign_id", "duplicate_id", "foreign_trigger", "missing_quest", "failed_without_failure", "extra_section"])
def test_invalid_content_revision_fails_without_mutating_the_saved_artifact(fault):
    original = source()
    before = copy.deepcopy(original)
    wire = project_content_revision(original, ["quest_hooks"] if fault == "missing_quest" else ["npc_archetypes", "quest_hooks"])
    quests = wire["quest_hooks"]["content"]["quests"]
    if fault == "foreign_id":
        quests[0]["id"] = "not-an-existing-quest"
    elif fault == "duplicate_id":
        quests.append(copy.deepcopy(quests[0]))
    elif fault == "foreign_trigger":
        wire["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["trigger"] = "not-an-existing-trigger"
    elif fault == "missing_quest":
        quests.clear()
    elif fault == "failed_without_failure":
        quests[0]["failure_states"] = []
        wire["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["stage"] = "failed"
    else:
        wire["unrelated"] = {}
    with pytest.raises(ValueError):
        assemble_content_revision(original, wire)
    assert original == before


def test_new_records_do_not_reuse_existing_keys_or_removed_objective_flags():
    from app.design_agent.content_draft import assemble_content_draft
    from test_nvidia_design_agent_provider import content_draft_fixture
    original = assemble_content_draft(content_draft_fixture(governed_artifact()))
    wire = project_content_revision(original, ["npc_archetypes", "quest_hooks"])
    quest = wire["quest_hooks"]["content"]["quests"][0]
    quest["objectives"][0]["objective"] = "Inspect the guards before clearing them"
    quest["objectives"][0]["completion_action"] = "Inspect the guards without defeating them"
    added = copy.deepcopy(quest)
    added.update(id=None, title="Proposed route check")
    wire["quest_hooks"]["content"]["quests"].append(added)
    line = wire["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    line.update(trigger=None, quest_index=1)
    added_npc = copy.deepcopy(wire["npc_archetypes"]["content"]["npcs"][0])
    added_npc["name"] = "New scout"
    wire["npc_archetypes"]["content"]["npcs"].append(added_npc)
    result = assemble_content_revision(original, wire)
    old = original["quest_hooks"]["content"]["quests"][0]
    revised, new = result["quest_hooks"]["content"]["quests"]
    assert revised["id"] == old["id"] and new["id"] != old["id"]
    assert revised["state_contract"]["objectives"][0]["flag"] != old["state_contract"]["objectives"][0]["flag"]
    assert revised["state_contract"]["objectives"][1] == old["state_contract"]["objectives"][1]
    mapping = result["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    assert mapping["eligibility"]["quest_id"] == new["id"]
    assert mapping["trigger"] != original["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["trigger"]
    assert result["npc_archetypes"]["content"]["npcs"][1]["dialogue_triggers"][0]["trigger"] != mapping["trigger"]


@pytest.mark.parametrize("fault", ["missing_restart", "foreign_trigger", "unreadable_failure", "unreadable_action"])
def test_invalid_revision_schema_is_not_repaired_into_different_content(fault):
    import httpx
    from app.design_agent.llm_provider import CompletionRequest, NvidiaProvider, NvidiaStructuredOutputError
    from test_design_agent_llm_provider import _completion
    original = source()
    targets = ["npc_archetypes", "quest_hooks"]
    wire = project_content_revision(original, targets)
    if fault == "missing_restart":
        wire["quest_hooks"]["content"]["quests"][0].pop("restart_action")
    elif fault == "foreign_trigger":
        wire["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["trigger"] = "npc_1_progress_1"
    elif fault == "unreadable_action":
        wire["quest_hooks"]["content"]["quests"][0]["objectives"][0]["completion_action"] = "quest_completed"
    else:
        wire["quest_hooks"]["content"]["quests"][0]["failure_states"] = [":{"]
    calls = []
    def respond(request):
        calls.append(request)
        return _completion(json.dumps(wire), input_tokens=123, output_tokens=45)
    llm = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=True,
                        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond)))
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        llm.complete(CompletionRequest(node_name="revise", messages=[], response_model=content_revision_model(targets, original)))
    assert len(calls) == 1 and caught.value.diagnostics["repair_skipped"] == "governed_schema_failure"
    assert caught.value.diagnostics["completions"][0]["input_tokens"] == 123


@pytest.mark.parametrize("fault", ["foreign_quest", "foreign_trigger", "other_npc_trigger", "renamed_npc_trigger"])
def test_wire_identity_selectors_are_scoped_to_the_frozen_artifact(fault):
    from pydantic import ValidationError
    original = source()
    other = copy.deepcopy(original["npc_archetypes"]["content"]["npcs"][0])
    other["name"] = "Other scout"
    other["dialogue_triggers"][0]["trigger"] = "other_scout_progress"
    original["npc_archetypes"]["content"]["npcs"].append(other)
    before = copy.deepcopy(original)
    targets = ["npc_archetypes", "quest_hooks"]
    wire = project_content_revision(original, targets)
    model = content_revision_model(targets, original)
    model.model_validate(wire)
    ids = set(citation for target in targets for citation in original[target]["citations"])
    grounded = grounded_response_model(model, [{"chunk_id": identity, "matched_sections": targets} for identity in ids])
    grounded.model_validate(wire)
    npc = wire["npc_archetypes"]["content"]["npcs"][0]
    if fault == "foreign_quest":
        wire["quest_hooks"]["content"]["quests"][0]["id"] = "invented_quest"
    elif fault == "foreign_trigger":
        npc["dialogue_triggers"][0]["trigger"] = "npc_1_progress_1"
    elif fault == "other_npc_trigger":
        npc["dialogue_triggers"][0]["trigger"] = "other_scout_progress"
    else:
        npc["name"] = "New scout"
    for validator in (model, grounded):
        with pytest.raises(ValidationError):
            validator.model_validate(wire)
    assert original == before


@pytest.mark.parametrize("field,value", [
    ("completion_action", "quest_completed"), ("failure_states", ":{"),
    ("failure_states", "quest_failed"), ("restart_action", "restart"),
])
def test_content_wire_requires_readable_actions_before_assembly(field, value):
    from pydantic import ValidationError
    from app.design_agent.content_draft import ContentBlueprintDraft
    from test_nvidia_design_agent_provider import content_draft_fixture
    original = source()
    generated = content_draft_fixture(original)
    revised = project_content_revision(original, ["quest_hooks"])
    for payload, model in ((generated, ContentBlueprintDraft),
                           (revised, content_revision_model(["quest_hooks"], original))):
        quest = payload["quest_hooks"]["content"]["quests"][0]
        if field == "completion_action":
            quest["objectives"][0][field] = value
        else:
            quest[field] = [value] if field == "failure_states" else value
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_historical_short_failure_label_uses_its_existing_readable_action_without_changing_keys():
    original = source()
    quest = original["quest_hooks"]["content"]["quests"][0]
    quest["failure_states"] = ["Death"]
    before = copy.deepcopy(original)
    wire = project_content_revision(original, ["quest_hooks"])
    event = quest["state_contract"]["failure"]["events"][0]
    assert wire["quest_hooks"]["content"]["quests"][0]["failure_states"] == [quest["state_contract"]["event_actions"][event]]
    rebuilt = assemble_content_revision(original, wire)
    assert rebuilt["quest_hooks"]["content"]["quests"][0]["state_contract"] == quest["state_contract"]
    assert original == before


def test_quest_action_schema_uses_json_strings_not_a_raw_regex_grammar():
    from pydantic import TypeAdapter
    from app.design_agent.contracts import QuestEventAction
    schema = TypeAdapter(QuestEventAction).json_schema()
    assert schema["type"] == "string"
    assert schema["minLength"] == 3 and schema["maxLength"] == 1000
    assert "pattern" not in schema


@pytest.mark.parametrize("value,valid", [
    ("Clear all guards", True),
    ('Player selects "Restart attempt"', True),
    (r"Player follows C:\routes\north", True),
    ("Player\nconfirms restart", True),
    ("खिलाड़ी पुनः आरंभ करता है", True),
    ("Player\u00a0confirms restart", True),
    ("quest_completed", False),
    (":{", False),
    ("   ", False),
    (" a ", False),
    ("Clear " + "x" * 995, False),
])
def test_quest_action_readability_and_length_still_apply_locally(value, valid):
    from pydantic import TypeAdapter, ValidationError
    from app.design_agent.contracts import QuestEventAction
    adapter = TypeAdapter(QuestEventAction)
    if valid:
        assert adapter.validate_python(value) == value
        assert adapter.validate_json(json.dumps(value)) == value
    else:
        with pytest.raises(ValidationError):
            adapter.validate_python(value)


def test_native_revision_keeps_action_validation_without_exporting_the_regex():
    import httpx
    from app.design_agent.llm_provider import CompletionRequest, NvidiaProvider, NvidiaStructuredOutputError
    from test_design_agent_llm_provider import _completion
    original = source()
    targets = ["quest_hooks"]
    model = content_revision_model(targets, original)
    wire = project_content_revision(original, targets)
    wire["quest_hooks"]["content"]["quests"][0]["objectives"][0]["completion_action"] = "quest_completed"
    calls = []
    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        schema = payload["response_format"]["json_schema"]["schema"]
        assert "pattern" not in schema["$defs"]["DraftObjective"]["properties"]["completion_action"]
        assert payload["response_format"]["json_schema"]["strict"] is True
        return _completion(json.dumps(wire))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=True,
                                  key_reader=lambda _: "offline-only", client=client)
        with pytest.raises(NvidiaStructuredOutputError) as caught:
            provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=model, guided_json=True))
    assert len(calls) == 1
    assert caught.value.diagnostics["repair_skipped"] == "governed_schema_failure"


def test_field_replacements_preserve_scope_identity_and_reject_invalid_edits():
    from app.design_agent.content_draft import assemble_content_field_revision, content_field_revision_model
    from app.design_agent.grounding import validate_structured_revision
    original = source()
    original["summary"].update(content={"description": None}, citations=[])
    before = copy.deepcopy(original)
    ids = list(dict.fromkeys(value for section in original.values() for value in section["citations"]))
    evidence = [{"chunk_id": value, "content": "Mira guards the training pass. Clear guards and raise the flag.",
                 "matched_sections": list(original)} for value in ids]
    targets = ["summary", "npc_archetypes", "quest_hooks"]
    empty = copy.deepcopy(original)
    quest = empty["quest_hooks"]["content"]["quests"][0]
    quest["failure_states"] = []
    quest["state_contract"]["event_actions"] = {item["event"]: quest["state_contract"]["event_actions"][item["event"]]
                                                for item in quest["state_contract"]["objectives"]}
    quest["state_contract"].update(failure=None, restart=None)
    patch_model = content_field_revision_model(targets, empty)
    schema = patch_model.model_json_schema()
    def resolve(value):
        return schema["$defs"][value["$ref"].rsplit("/", 1)[-1]] if "$ref" in value else value
    items = resolve(schema["properties"]["changes"]["items"])
    branches = [resolve(branch) for branch in items.get("anyOf", [items])]
    native = {path: branch["properties"]["replacement"] for branch in branches
              for path in branch["properties"]["artifact_path"].get("enum", [branch["properties"]["artifact_path"].get("const")])}
    for path, valid, invalid, expected_type in (
        ("/summary/content/description", "A source-backed training adventure.", {}, "string"),
        ("/summary/citations", [ids[0]], "wrong shape", "array"),
        ("/summary/confidence", "Low", "Certain", "string"),
        ("/quest_hooks/content/quests/0/restart_action", 'Player selects "Restart attempt"', {"type": "ui_confirm"}, "string"),
        ("/quest_hooks/content/quests/0/failure_states", ["Player abandons the active attempt"], [{"trigger": "abandon_quest"}], "array"),
        ("/quest_hooks/content/quests/0/objectives", [{"objective": "Clear all guards", "completion_action": "Defeat all guards"}], "wrong shape", "array"),
        ("/npc_archetypes/content/npcs/0/dialogue_triggers/0/text", "The pass still needs your aid.", {"text": "wrong shape"}, "string"),
        ("/npc_archetypes/content/npcs/0/dialogue_triggers/0/quest_index", 0, True, "integer"),
    ):
        assert expected_type in {value.get("type") for value in native[path].get("anyOf", [native[path]])}
        payload = {"changes": [{"artifact_path": path, "replacement": valid}]}
        patch_model.model_validate(payload)
        payload["changes"][0]["replacement"] = invalid
        with pytest.raises(ValueError):
            patch_model.model_validate(payload)
    nullable = {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/restart_action", "replacement": None}]}
    patch_model.model_validate(nullable)
    assert native["/quest_hooks/content/quests/0/failure_states"]["items"]["type"] == "string"
    assert native["/quest_hooks/content/quests/0/objectives"]["maxItems"] == 4
    text_path = "/npc_archetypes/content/npcs/0/dialogue_triggers/0/text"
    assert native[text_path]["maxLength"] == 1000
    for path, invalid in ((text_path, "x" * 1001),
                          ("/quest_hooks/content/quests/0/restart_action", "quest_completed"),
                          ("/npc_archetypes/content/npcs/0/dialogue_triggers/0/quest_index", 2)):
        with pytest.raises(ValueError):
            patch_model.model_validate({"changes": [{"artifact_path": path, "replacement": invalid}]})
    action_changes = {"changes": [
        {"artifact_path": "/quest_hooks/content/quests/0/failure_states", "replacement": ["Player abandons the active attempt"]},
        {"artifact_path": "/quest_hooks/content/quests/0/restart_action", "replacement": 'Player selects "Restart attempt"'},
    ]}
    assembled = assemble_content_field_revision(empty, action_changes, ["quest_hooks"], evidence, defer_runtime=True)
    state = assembled["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert state["event_actions"][state["failure"]["events"][0]] == action_changes["changes"][0]["replacement"][0]
    assert state["event_actions"][state["restart"]["event"]] == action_changes["changes"][1]["replacement"]
    assert empty["quest_hooks"]["content"]["quests"][0]["state_contract"]["restart"] is None
    changes = [
        {"artifact_path": "/summary/content/description", "replacement": "A source-backed training adventure."},
        {"artifact_path": "/summary/citations", "replacement": [ids[0]]},
        {"artifact_path": "/npc_archetypes/content/npcs/0/dialogue_triggers/0/text", "replacement": "There is still work to do at the pass."},
        {"artifact_path": "/quest_hooks/content/quests/0/objectives/0/objective", "replacement": "Clear all guards"},
    ]
    result = assemble_content_field_revision(original, {"changes": changes}, targets, evidence, defer_runtime=True)
    merged = {**original, **result}
    assert validate_structured_revision(original, merged, "Correct selected fields", targets, evidence=evidence)
    assert result["summary"]["content"]["description"] == changes[0]["replacement"]
    old = original["quest_hooks"]["content"]["quests"][0]["state_contract"]
    new = result["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert new["objectives"][0] == {**old["objectives"][0], "objective": "Clear all guards"}
    assert new["event_actions"] == old["event_actions"] and new["completion"] == old["completion"]
    assert all(merged[key] == original[key] for key in original if key not in targets)
    assert original == before
    assert len(json.dumps({"changes": changes})) < len(json.dumps(project_content_revision(merged, targets))) / 2
    for bad in (
        {"changes": []},
        {"changes": [changes[0], changes[0]]},
        {"changes": [{"artifact_path": "/art_style_direction/content/visual_theme", "replacement": "Other"}]},
        {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/id", "replacement": "foreign"}]},
        {"changes": [{"artifact_path": "/npc_archetypes/content/npcs/0/dialogue_triggers/0/trigger", "replacement": "foreign"}]},
        {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/state_contract/completion/mode", "replacement": "any"}]},
        {"changes": [{"artifact_path": "/summary/citations", "replacement": ["foreign"]}]},
        {"changes": [{"artifact_path": "/quest_hooks/content/quests", "replacement": []}, changes[-1]]},
        {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/objectives", "replacement": "invalid"}]},
        {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/runtime", "replacement": {"npc_slug": "invented"}}]},
    ):
        with pytest.raises(ValueError):
            assemble_content_field_revision(original, bad, targets, evidence, defer_runtime=True)
        assert original == before

    import httpx
    from app.design_agent.llm_provider import NvidiaProvider, NvidiaStructuredOutputError
    from test_design_agent_llm_provider import _completion
    for bad in (
        {"changes": [{"artifact_path": "/unselected/content", "replacement": {}}]},
        {"changes": [{"artifact_path": "/summary/citations", "replacement": ["foreign"]}]},
        {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/restart_action", "replacement": {"type": "ui_confirm"}}]},
    ):
        calls = []
        def respond(request):
            calls.append(request)
            return _completion(json.dumps(bad))
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            provider = NvidiaDesignAgentProvider(llm_provider=NvidiaProvider(base_url="https://example.invalid/v1",
                timeout_seconds=1, repair_enabled=True, key_reader=lambda _: "offline-only", client=client))
            with pytest.raises(NvidiaStructuredOutputError):
                provider.revise(original, evidence, "Correct selected fields", targets, review_request={**REQUEST, "defer_runtime": True})
        assert len(calls) == 1 and original == before


def test_governed_provider_applies_typed_quest_changes_without_regenerating_sections():
    import httpx
    from app.design_agent.llm_provider import NvidiaProvider
    from app.design_agent.grounding import validate_structured_revision
    from test_design_agent_llm_provider import _completion

    original = source()
    before = copy.deepcopy(original)
    evidence = [{"chunk_id": value, "content": "Mira guards the training pass. Clear guards and raise the flag.",
                 "matched_sections": list(original)} for value in original["quest_hooks"]["citations"]]
    cause = "Player explicitly confirms abandonment of the active quest"
    wire = {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/failure_states", "replacement": [cause]}]}
    sends = []
    def respond(request):
        sends.append(json.loads(request.content))
        return _completion(json.dumps(wire))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = NvidiaDesignAgentProvider(llm_provider=NvidiaProvider(base_url="https://example.invalid/v1",
            timeout_seconds=1, repair_enabled=True, key_reader=lambda _: "offline-only", client=client))
        result = provider.revise(original, evidence, "Replace the quest failure with player-confirmed abandonment.",
                                 ["quest_hooks"], review_request=REQUEST)
    quest = result.content["quest_hooks"]["content"]["quests"][0]
    assert quest["failure_states"] == [cause]
    assert quest["state_contract"]["event_actions"][quest["state_contract"]["failure"]["events"][0]] == cause
    assert quest["state_contract"]["objectives"] == before["quest_hooks"]["content"]["quests"][0]["state_contract"]["objectives"]
    assert quest["reward"] == before["quest_hooks"]["content"]["quests"][0]["reward"]
    assert all(result.content[key] == before[key] for key in before if key != "quest_hooks")
    validate_structured_revision(before, result.content, "Replace the failure cause", ["quest_hooks"], evidence=evidence)
    assert len(sends) == 1 and result.metadata["repair_attempts"] == 0 and original == before


def test_field_revision_repair_preserves_all_values_and_rejects_changed_content():
    from app.design_agent.content_draft import content_field_revision_model
    from app.design_agent.llm_provider import NvidiaStructuredOutputError
    from test_json_closer_recovery import invoke

    model = content_field_revision_model(["quest_hooks"], source())
    wire = {"changes": [{"artifact_path": "/quest_hooks/content/quests/0/failure_states",
                         "replacement": ["Player confirms abandonment of the active quest"]}]}
    raw = json.dumps(wire) + "}"
    result, sends = invoke(raw, model=model, repair=True, repaired_raw=json.dumps(wire))
    assert result.content == wire and len(sends) == 2
    assert result.metadata["repair_attempts"] == 1 and not result.metadata["local_recovery"]
    for invalid in ({"changes": []}, {"changes": [{**wire["changes"][0], "replacement": ["Player is defeated during the active quest"]}]}):
        with pytest.raises(NvidiaStructuredOutputError):
            invoke(raw, model=model, repair=True, repaired_raw=json.dumps(invalid))
    for unsafe in (raw + "}", raw + '{"discarded":true}', '"unfinished', '{"changes":[]} prose'):
        with pytest.raises(NvidiaStructuredOutputError):
            invoke(unsafe, model=model, repair=True, repaired_raw=json.dumps(wire))
