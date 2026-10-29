"""Synthetic offline proof only; no hosted generation or approval."""
import copy
import json

import httpx
import pytest
from pydantic import ValidationError

from app.design_agent.llm_provider import CompletionRequest, NvidiaProvider
from test_design_agent_llm_provider import _completion
from test_design_contract_v2 import governed_artifact
from tools.content_only_qa import assemble_content_pack, content_response_model


def scaffold():
    full = governed_artifact()
    pack = {key: full[key] for key in ("npc_archetypes", "quest_hooks")}
    npc = pack["npc_archetypes"]["content"]["npcs"][0]
    progress = npc["dialogue_triggers"][0]
    greeting = {**copy.deepcopy(progress), "trigger": "first_greeting", "situation": "First interaction with the selected NPC.", "eligibility": {
        "stage": "greeting", "quest_id": None, "lifecycle": None, "progress": "any"}}
    completion = {**copy.deepcopy(progress), "trigger": "quest_completion", "situation": "Selected quest completed with all objective flags true.", "eligibility": {
        **progress["eligibility"], "stage": "completion", "lifecycle": "completed", "progress": "complete"}}
    npc["dialogue_triggers"] = [completion, greeting, progress]  # Deliberately not stage order.
    return pack


def response(pack):
    state = pack["quest_hooks"]["content"]["quests"][0]["state_contract"]
    actions = {item["event"]: f"Player completes the action: {item['objective']}." for item in state["objectives"]}
    actions.update({event: "The player's health reaches zero during an active attempt." for event in state["failure"]["events"]})
    actions[state["restart"]["event"]] = "Player explicitly confirms Restart Quest for a new attempt."
    return {"greeting": "Welcome, traveler.", "progress": "The pass is not yet secured.",
        "completion": "Both tasks are finished; the pass is secured.",
        "npc_integration_notes": ["In the designer-selected interaction handler, check the slot eligibility before playing its line."],
        "quest_integration_notes": ["Connect designer-confirmed gameplay events to the existing flags; inspect lifecycle after each event."],
        "event_actions": dict(actions)}


@pytest.mark.parametrize("reserved_event_name", [False, True])
def test_mocked_content_generation_assembles_by_stage_without_changing_the_scaffold(reserved_event_name):
    pack = scaffold()
    pack["quest_hooks"]["content"]["quests"][0]["implementation_notes"] = [
        "Keep the designer-confirmed activation event.", "Contract check (not executed): stale event description."]
    if reserved_event_name:
        state = pack["quest_hooks"]["content"]["quests"][0]["state_contract"]
        old_event = state["objectives"][0]["event"]
        state["objectives"][0]["event"] = "model_config"
        state["event_actions"] = {"model_config" if key == old_event else key: value for key, value in state["event_actions"].items()}
    authored = response(pack)
    before = copy.deepcopy((pack, authored))
    model = content_response_model(pack)
    schema = model.model_json_schema()
    assert set(schema["properties"]) == {"greeting", "progress", "completion", "npc_integration_notes", "quest_integration_notes", "event_actions"}
    assert set(schema["properties"]["event_actions"]["required"]) == set(authored["event_actions"])
    assert "propertyNames" not in schema["properties"]["event_actions"]
    assert schema["properties"]["event_actions"]["additionalProperties"] is False
    assert set(schema["properties"]["event_actions"]["properties"]) == set(authored["event_actions"])
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        assert calls[-1]["response_format"]["json_schema"]["schema"] == model.model_json_schema()
        return _completion(json.dumps(authored))
    provider = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=False,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond)))
    result = provider.complete(CompletionRequest(node_name="generate_blueprint", messages=[], response_model=model, guided_json=True))
    assembled = assemble_content_pack(pack, result.content)
    npc = assembled["npc_archetypes"]["content"]["npcs"][0]
    for mapping in npc["dialogue_triggers"]:
        assert mapping["text"] == authored[mapping["eligibility"]["stage"]]
        assert mapping["text"] in mapping["manual_test"]
        original = next(item for item in pack["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]
                        if item["eligibility"]["stage"] == mapping["eligibility"]["stage"])
        assert mapping["eligibility"] == original["eligibility"] and mapping["repeat_policy"] == original["repeat_policy"]
    assert npc["dialogue_hooks"] == [mapping["text"] for mapping in npc["dialogue_triggers"]]
    for key in ("name", "source_chunk_ids", "dialogue_style"):
        assert npc[key] == pack["npc_archetypes"]["content"]["npcs"][0][key]
    quest = assembled["quest_hooks"]["content"]["quests"][0]
    original_quest = pack["quest_hooks"]["content"]["quests"][0]
    expected_state = {**original_quest["state_contract"], "event_actions": authored["event_actions"]}
    assert quest["state_contract"] == expected_state
    for key in ("id", "title", "objective", "objectives", "reward", "source_chunk_ids", "dependencies", "failure_states"):
        assert quest[key] == original_quest[key]
    assert quest["runtime"] is None and any("unverified proposals" in item for item in quest["assumptions"])
    notes = "\n".join(quest["implementation_notes"])
    assert "stale event description" not in notes and "Keep the designer-confirmed activation event." in notes
    assert authored["event_actions"][next(iter(authored["event_actions"]))] in notes
    assert len(calls) == 1 and (pack, authored) == before


@pytest.mark.parametrize("fault", ["missing_line", "blank_notes", "foreign_id", "wrong_event", "missing_event"])
def test_content_cannot_supply_frozen_fields_or_omit_required_work(fault):
    pack = scaffold()
    authored = response(pack)
    if fault == "missing_line":
        authored.pop("greeting")
    elif fault == "blank_notes":
        authored["quest_integration_notes"] = ["  "]
    elif fault == "foreign_id":
        authored["quest_id"] = "0"
    elif fault == "wrong_event":
        authored["event_actions"].pop(next(iter(authored["event_actions"])))
        authored["event_actions"]["invented_event"] = "Invented gameplay action"
    else:
        authored["event_actions"].pop(next(iter(authored["event_actions"])))
    before = copy.deepcopy((pack, authored))
    with pytest.raises(ValidationError):
        assemble_content_pack(pack, authored)
    assert (pack, authored) == before


def test_scaffold_requires_explicit_distinct_slots_and_valid_quest_references():
    pack = scaffold()
    npc = pack["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_triggers"][0]["eligibility"]["quest_id"] = "0"
    with pytest.raises(ValidationError, match="selected quest"):
        content_response_model(pack)
    npc["dialogue_triggers"] = [npc["dialogue_triggers"][1]] * 3
    with pytest.raises(ValidationError, match="select greeting, progress and completion"):
        content_response_model(pack)
    pack = scaffold()
    pack["summary"] = {"content": {"premise": "Do not silently discard an unselected section."}}
    with pytest.raises(ValidationError, match="Extra inputs"):
        content_response_model(pack)
