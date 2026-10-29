"""Regressions from the real PATCH trigger/line mismatch; no hosted calls."""
import pytest
from pydantic import ValidationError

from app.design_agent.contracts import BlueprintContent
from app.design_agent.grounding import assess_artifact_quality, validate_generated_blueprint
from app.design_agent.llm_provider import CompletionResult
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from app.design_agent.provider import MockDesignAgentProvider


LINES = [
    "That link is trying too hard. Check the URL before you trust it.",
    "A file called homework_final_REAL_REAL.exe is already confessing.",
    "Firewall ahead. Literal this time. Someone had fun with the simulation.",
]
EVIDENCE = [{
    "chunk_id": "patch", "content": "PATCH gives warnings. " + " ".join(LINES),
    "matched_sections": ["npc_archetypes"],
}]


def artifact():
    content = MockDesignAgentProvider().generate({"objective": "Design a game"}, EVIDENCE).content
    content["npc_archetypes"]["content"]["npcs"] = [{
        "name": "PATCH", "archetype": "Companion", "dialogue_style": "Funny warnings",
        "source_chunk_ids": ["patch"], "dialogue_hooks": LINES,
        "dialogue_triggers": [{
            "trigger": event, "situation": situation, "text": line,
            "repeat_policy": "Once per encounter; reset when the encounter ends.",
            "manual_test": f"Simulate {event}; expect exactly '{line}', repeat and verify suppression.",
        } for event, situation, line in zip(
            ["suspicious_link", "suspicious_file", "firewall_encounter"],
            ["Player selects an untrusted URL", "Player tries to open a suspicious executable", "Player reaches a firewall"],
            LINES,
        )],
    }]
    return content


def test_explicit_pairings_survive_validation_and_produce_matching_integration_notes():
    original = artifact()
    result = validate_generated_blueprint(original, EVIDENCE)
    npc = result["npc_archetypes"]["content"]["npcs"][0]
    assert len(npc["dialogue_triggers"]) == 3
    for pairing in npc["dialogue_triggers"]:
        assert any(pairing["trigger"] in note and pairing["text"] in note
                   and pairing["manual_test"] in note for note in npc["implementation_notes"])
    assert original == artifact(), "Validation must not mutate caller data"


def test_revision_rebuilds_integration_notes_without_stale_pairings():
    import copy

    original = artifact()
    old_event_notes = [
        "Proposal - Event: Player selects an untrusted URL; State: Show PATCH warning popup; Check: Warning text matches source line.",
        "proposal \u2014 event: Player opens a file; state: Play warning dialogue; check: Reset on scanner use.",
        "Event: Player reaches firewall;\nState: Show subtitle; Check: Play the old line.",
    ]
    profile_notes = [
        "Keep captions readable and do not block player movement.",
        "Event: NPC spawns; State: Register companion with navigation; Check: Companion follows the player.",
    ]
    original["npc_archetypes"]["content"]["npcs"][0]["implementation_notes"] = old_event_notes + profile_notes
    untouched = copy.deepcopy(original)
    before = validate_generated_blueprint(original, EVIDENCE)
    assert original == untouched
    assert all(note not in before["npc_archetypes"]["content"]["npcs"][0]["implementation_notes"]
               for note in old_event_notes)
    assert validate_generated_blueprint(before, EVIDENCE) == before
    npc = before["npc_archetypes"]["content"]["npcs"][0]
    revised_line = "Check the URL before you trust it."
    npc["dialogue_hooks"][0] = revised_line
    npc["dialogue_triggers"][0].update({
        "text": revised_line,
        "manual_test": f"Click the untrusted link; expect '{revised_line}', then verify suppression.",
    })
    revised = validate_generated_blueprint(before, EVIDENCE)
    notes = revised["npc_archetypes"]["content"]["npcs"][0]["implementation_notes"]
    mapping_notes = [note for note in notes if note.startswith("Dialogue trigger proposal '")]
    assert len(mapping_notes) == 3
    assert all(note in notes for note in profile_notes)
    assert not any(LINES[0] in note for note in mapping_notes)
    assert not any("first-contact lines" in note for note in notes)
    assert any(revised_line in note for note in mapping_notes)

    # No structured mapping means a legacy event note must not be discarded.
    legacy = copy.deepcopy(original)
    legacy["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"] = []
    legacy_notes = validate_generated_blueprint(legacy, EVIDENCE)["npc_archetypes"]["content"]["npcs"][0]["implementation_notes"]
    assert all(note in legacy_notes for note in old_event_notes + profile_notes)


@pytest.mark.parametrize("fault", ["orphan", "duplicate", "missing_line"])
def test_broken_pairing_references_are_rejected(fault):
    content = artifact()
    mappings = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]
    if fault == "orphan":
        mappings[0]["text"] = "A different line not in the dialogue pack."
    elif fault == "duplicate":
        mappings[1]["trigger"] = mappings[0]["trigger"]
    elif fault == "missing_line":
        mappings.pop()
    with pytest.raises(ValueError, match="dialogue trigger"):
        validate_generated_blueprint(content, EVIDENCE)


def test_blank_mapping_test_and_unknown_fields_are_invalid():
    content = artifact()
    pairing = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    pairing["manual_test"] = "  "
    pairing["verified_by_model"] = True
    with pytest.raises(ValidationError):
        BlueprintContent.model_validate(content)


def test_source_quoted_lines_do_not_make_generated_trigger_choices_factual():
    result = validate_generated_blueprint(artifact(), EVIDENCE)
    npc = result["npc_archetypes"]["content"]["npcs"][0]
    assert any("trigger mappings" in item for item in npc["assumptions"])
    assert not assess_artifact_quality(result)["passed"]


def test_structurally_valid_swapped_semantics_are_never_automatically_certified():
    content = artifact()
    mappings = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]
    mappings[0]["text"], mappings[1]["text"] = mappings[1]["text"], mappings[0]["text"]
    for mapping in mappings:
        mapping["manual_test"] = f"Simulate {mapping['trigger']}; expect '{mapping['text']}'."
    result = validate_generated_blueprint(content, EVIDENCE)
    assert any("check each situation/line pairing" in item
               for item in result["npc_archetypes"]["content"]["npcs"][0]["assumptions"])
    assert not assess_artifact_quality(result)["passed"]


def test_legacy_unstructured_mapping_is_blocked_not_silently_repaired():
    content = artifact()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    del npc["dialogue_triggers"]
    npc["implementation_notes"] = [
        f'Trigger mapping:\n- suspicious_link: "{LINES[1]}" triggered on link click.'
    ]
    result = validate_generated_blueprint(content, EVIDENCE)
    assert any("unstructured trigger" in warning for warning in result["npc_archetypes"]["warnings"])
    with pytest.raises(ValueError, match="unstructured trigger"):
        validate_generated_blueprint(content, EVIDENCE, require_actionable=True,
                                     actionable_sections={"npc_archetypes"})


def test_hosted_revision_contract_requests_semantic_pairs_not_positional_lists():
    class Capture:
        def complete(self, request):
            self.request = request
            return CompletionResult(
                content=request.response_model.model_validate({
                    "npc_archetypes": {"patches": [{
                        "name": "PATCH", "source_chunk_ids": ["patch"], "assumptions": [],
                        "dialogue_triggers": [{key: mapping[key] for key in (
                            "trigger", "situation", "text", "repeat_policy",
                        )} for mapping in artifact()["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]],
                    }]},
                }).model_dump(), provider_name="nvidia", model_name="fixture",
            )

    capture = Capture()
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    result = provider.revise(artifact(), EVIDENCE, "Fix the situation/line mapping.",
                             target_sections=["npc_archetypes"])
    prompt = capture.request.messages[1]["content"]
    assert "Check each pairing independently by meaning" in prompt
    assert "Each spoken line must fit that NPC and the described game event" in prompt
    assert "the server will derive those" in prompt
    assert len(result.content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]) == 3
