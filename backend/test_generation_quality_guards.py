"""Local regressions from the six-request CyberRakshak QA; no hosted calls."""
import copy

import pytest

from app.design_agent.contracts import DialogueTriggerMapping
from app.design_agent.grounding import assess_artifact_quality, validate_generated_blueprint
from test_dialogue_trigger_alignment import EVIDENCE, LINES, artifact


QUEST_SOURCE = {
    "chunk_id": "levels", "matched_sections": ["quest_hooks"],
    "content": "Level 1: Training Sandbox. Learn movement and combat. "
    "Level 2: Password Vault. Strong gates require correct password-token combinations. "
    "Level 3: Phishing Office. There are three story acts.",
}


def quest_artifact(failure):
    content = artifact()
    content["quest_hooks"]["content"]["quests"] = [{
        "id": "password-vault", "title": "Password Vault",
        "objective": "Strong gates require correct password-token combinations.",
        "source_chunk_ids": ["levels"],
        "objectives": ["Strong gates require correct password-token combinations."],
        "failure_states": [failure], "dependencies": [],
    }]
    return content


@pytest.mark.parametrize("old_test", [None, "Check a warning appears.", "Expect a stale line."])
def test_manual_test_is_derived_from_exact_current_line_and_policy(old_test):
    content = artifact()
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    mapping["repeat_policy"] = "Once per object per mission attempt; reset ONLY on mission restart."
    if old_test is None:
        mapping.pop("manual_test")
    else:
        mapping["manual_test"] = old_test
    before = copy.deepcopy(content)
    validated = validate_generated_blueprint(content, EVIDENCE)
    result = validated["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    assert result["text"] in result["manual_test"]
    assert result["situation"] in result["manual_test"]
    assert result["repeat_policy"] in result["manual_test"]
    assert "reset" in result["manual_test"].lower()
    assert "stale line" not in result["manual_test"]
    assert content == before
    assert validate_generated_blueprint(validated, EVIDENCE) == validated


def test_hosted_contract_does_not_require_a_duplicate_manual_test():
    assert "manual_test" not in DialogueTriggerMapping.model_json_schema()["required"]


def test_scene_integration_notes_are_visible_proposals_requiring_record_confirmation():
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from app.design_agent.grounding import validate_design_approval
    from test_quest_state_contract import typed_artifact
    content = typed_artifact()
    notes = [
        "Scene integration: Place Mira at the Watchtower overlooking Ash Pass. Dialogue triggers fire on player proximity and interaction.",
        "Scene integration: Quest activates when player enters Ash Pass zone. Objectives are tracked via state contract v1.",
    ]
    records = [content["npc_archetypes"]["content"]["npcs"][0],
               content["quest_hooks"]["content"]["quests"][0]]
    for record, note in zip(records, notes):
        record["implementation_notes"] = [note, "Manual verification: Check state eligibility before playing a line."]
    before = copy.deepcopy(content)
    evidence = [{"chunk_id": records[0]["source_chunk_ids"][0], "matched_sections": list(BLUEPRINT_SECTION_KEYS),
                 "content": "Version 1. Mira is a mentor. Check the route before moving. Clear the guards. Raise the Northern flag. Player dies during attempt."}]
    draft = validate_generated_blueprint(content, evidence)
    proposal = ("Scene integration notes are unverified implementation proposals; confirm placement, "
                "activation events and source compatibility before runtime use.")
    for section, key, note in zip(("npc_archetypes", "quest_hooks"), ("npcs", "quests"), notes):
        record = draft[section]["content"][key][0]
        assert "Scene integration proposal:" + note.split(":", 1)[1] in record["implementation_notes"]
        assert proposal in record["assumptions"]
        assert "Manual verification: Check state eligibility before playing a line." in record["implementation_notes"]
    assert content == before
    assert validate_generated_blueprint(draft, evidence) == draft
    pending = assess_artifact_quality(draft)["unresolved_assumptions"]
    scene_items = [item for item in pending if item["assumption"] == proposal]
    assert {item["section"] for item in scene_items} == {"npc_archetypes", "quest_hooks"}
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in pending if item["section"] != "quest_hooks" or item["assumption"] != proposal]
    score = assess_artifact_quality(draft, confirmations)
    assert "Integration readiness" in score["blockers"]
    assert score["unresolved_assumptions"] == [scene_items[1]]
    ready = {"verdict": "ready_for_review", "findings": []}
    with pytest.raises(ValueError, match="Integration readiness"):
        validate_design_approval(draft, evidence, ready, confirmations)
    all_confirmed = [{key: item[key] for key in ("section", "record_id", "assumption")} for item in pending]
    assert validate_design_approval(draft, evidence, ready, all_confirmed)["passed"]  # Pure gate, no runtime approval.
    tampered = copy.deepcopy(draft)
    for section, key in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
        tampered[section]["content"][key][0]["assumptions"].remove(proposal)
    without_scene = [item for item in all_confirmed if item["assumption"] != proposal]
    with pytest.raises(ValueError, match="Integration readiness"):
        validate_design_approval(tampered, evidence, ready, without_scene)


@pytest.mark.parametrize("name", ["Patch1", "PAT", "New Companion", ""])
def test_npc_identity_must_be_named_in_its_cited_evidence(name):
    content = artifact()
    content["npc_archetypes"]["content"]["npcs"][0]["name"] = name
    with pytest.raises(ValueError, match="identity"):
        validate_generated_blueprint(content, EVIDENCE)


def test_unrelated_uncited_name_does_not_ground_an_npc_identity():
    content = artifact()
    content["npc_archetypes"]["content"]["npcs"][0]["name"] = "Patch1"
    extra = {"chunk_id": "unrelated", "content": "Patch1", "matched_sections": ["summary"]}
    with pytest.raises(ValueError, match="identity"):
        validate_generated_blueprint(content, [*EVIDENCE, extra])


@pytest.mark.parametrize("fresh", [False, True])
def test_source_quote_reuse_is_visible_without_rejecting_valid_existing_dialogue(fresh):
    result = validate_generated_blueprint(artifact(), EVIDENCE, fresh_dialogue=fresh)
    assert result["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] == LINES
    assert any("reused source" in warning.lower() for warning in result["npc_archetypes"]["warnings"])
    assert ("Fresh dialogue" in assess_artifact_quality(result)["blockers"]) is fresh


@pytest.mark.parametrize("rule", [
    "Enter wrong password three times",
    "Enter wrong password 3 times",
    "Fail to complete drills within time limit",
])
def test_unsupported_failure_rule_is_a_specific_proposal_and_cannot_be_approved(rule):
    content = quest_artifact(rule)
    evidence = [*EVIDENCE, QUEST_SOURCE]
    draft = validate_generated_blueprint(content, evidence)
    quest = draft["quest_hooks"]["content"]["quests"][0]
    assert any(rule in assumption and "proposal" in assumption.lower() for assumption in quest["assumptions"])
    assert not assess_artifact_quality(draft)["passed"]
    # Even deleting an assumption in a client cannot turn it into a supported rule.
    quest["assumptions"] = []
    with pytest.raises(ValueError, match="unsupported failure rule"):
        validate_generated_blueprint(draft, evidence, require_actionable=True,
                                     actionable_sections={"quest_hooks"})


def test_source_supported_failure_rule_can_pass_actionable_validation():
    rule = "Enter wrong password three times"
    source = {**QUEST_SOURCE, "content": QUEST_SOURCE["content"] + " Failure: " + rule + "."}
    result = validate_generated_blueprint(quest_artifact(rule), [*EVIDENCE, source],
                                          require_actionable=True, actionable_sections={"quest_hooks"})
    assert result["quest_hooks"]["content"]["quests"][0]["failure_states"] == [rule]


@pytest.mark.parametrize("supported", [False, True])
def test_typed_event_descriptions_cannot_hide_an_invented_failure_timer(supported):
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from test_quest_state_contract import typed_artifact

    content = typed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    contract = quest["state_contract"]
    rule = "The countdown reaches 300 seconds during the active attempt"
    quest["failure_states"] = ["The active attempt ends"]
    contract["failure"]["events"] = ["attempt_ends"]
    contract["event_actions"] = {
        item["event"]: item["event"] for item in contract["objectives"]
    } | {"attempt_ends": rule, contract["restart"]["event"]: "Player explicitly confirms a new attempt"}
    source = "Version 1. Mira is a mentor. Clear the guards. Raise the Northern flag. The active attempt ends."
    source += " " + ". ".join(action for event, action in contract["event_actions"].items() if event != "attempt_ends")
    evidence = [{"chunk_id": quest["source_chunk_ids"][0], "matched_sections": list(BLUEPRINT_SECTION_KEYS),
                 "content": source + (" " + rule + "." if supported else "")}]
    before = copy.deepcopy(content)
    draft = validate_generated_blueprint(content, evidence)
    assert content == before
    if not supported:
        tampered = copy.deepcopy(content)
        tampered["quest_hooks"]["content"]["quests"][0]["assumptions"] = []
        with pytest.raises(ValueError, match="unsupported numeric detail.*300"):
            validate_generated_blueprint(tampered, evidence, require_actionable=True,
                                         actionable_sections={"quest_hooks"})
        assert any("event actions" in value for value in draft["quest_hooks"]["content"]["quests"][0]["assumptions"])
    else:
        assert not any("event actions" in value for value in draft["quest_hooks"]["content"]["quests"][0]["assumptions"])
        result = validate_generated_blueprint(draft, evidence, require_actionable=True,
                                              actionable_sections={"quest_hooks"})
        assert result["quest_hooks"]["content"]["quests"][0]["state_contract"]["event_actions"]["attempt_ends"] == rule


def test_npc_identity_accepts_case_and_unicode_without_substring_matches():
    content = artifact()
    content["npc_archetypes"]["content"]["npcs"][0]["name"] = "पैच"
    evidence = [{**EVIDENCE[0], "content": "पैच gives warnings. " + " ".join(LINES)}]
    assert validate_generated_blueprint(content, evidence)["npc_archetypes"]["content"]["npcs"][0]["name"] == "पैच"
