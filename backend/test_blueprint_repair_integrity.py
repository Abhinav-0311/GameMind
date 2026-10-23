"""Schema repair is not permission to rewrite a generated design."""
import copy
import json

import pytest

from app.design_agent.contracts import BlueprintContent
from app.design_agent.llm_provider import NvidiaStructuredOutputError
from test_json_closer_recovery import invoke
from test_revision_completeness_guards import complete_artifact


def invalid_metadata_blueprint():
    content = complete_artifact()
    content["summary"]["confidence"] = "not-a-confidence"
    return content


@pytest.mark.parametrize("change", ["line", "drop_npc", "drop_quest", "objective", "level", "runtime"])
def test_repair_cannot_change_or_discard_readable_schema_valid_design_values(change):
    original = invalid_metadata_blueprint()
    original["level_design_suggestions"]["content"] = {"levels": [{"title": "Relay", "checkpoint": False}]}
    repaired = copy.deepcopy(original)
    repaired["summary"]["confidence"] = "High"
    if change == "line":
        repaired["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] = ["Run into the hazard."]
    elif change == "drop_npc":
        repaired["npc_archetypes"]["content"]["npcs"] = []
    elif change == "drop_quest":
        repaired["quest_hooks"]["content"]["quests"] = []
    elif change == "objective":
        repaired["quest_hooks"]["content"]["quests"][0]["objectives"] = ["Collect a different key."]
    elif change == "level":
        repaired["level_design_suggestions"]["content"]["levels"][0]["checkpoint"] = True
    else:
        repaired["unity_runtime_preview"]["content"] = {"reward": 1000}
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke(json.dumps(original), model=BlueprintContent, repair=True, repaired_raw=json.dumps(repaired))
    assert caught.value.attempts == 2
    assert caught.value.code == "structured_output_invalid"
    assert "Run into the hazard" not in str(caught.value) + json.dumps(caught.value.diagnostics)


def test_metadata_shape_repair_preserves_design_data_and_still_succeeds():
    result, calls = invoke(json.dumps(invalid_metadata_blueprint()), model=BlueprintContent,
                           repair=True, repaired_raw=json.dumps(complete_artifact()))
    assert len(calls) == 2 and result.content == complete_artifact()
    assert result.metadata["repair_attempts"] == 1


@pytest.mark.parametrize("raw", ['{"summary":', '{"summary":{"content":{"text":"unfinished',
                                 'commentary ' + json.dumps(invalid_metadata_blueprint()),
                                 '```json\n' + json.dumps(invalid_metadata_blueprint())])
def test_unreadable_or_ambiguous_original_cannot_authorize_a_replacement_design(raw):
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke(raw, model=BlueprintContent, repair=True, repaired_raw=json.dumps(complete_artifact()))
    # The repaired JSON is valid; it failed preservation, not its JSON syntax.
    assert caught.value.diagnostics["completions"][-1]["failure_kind"] == "validation"


def test_readable_outer_brace_failure_can_be_repaired_without_rewriting_design():
    original = complete_artifact()
    # Missing metadata prevents local closer recovery, but the design data is intact.
    original["summary"].pop("warnings")
    raw = json.dumps(original)[:-1]
    result, calls = invoke(raw, model=BlueprintContent, repair=True,
                           repaired_raw=json.dumps(complete_artifact()))
    assert len(calls) == 2 and result.content == complete_artifact()


def test_missing_section_may_be_added_only_as_an_empty_schema_placeholder():
    original = complete_artifact()
    original.pop("art_style_direction")
    repaired = complete_artifact()
    repaired["art_style_direction"] = {"content": {}, "citations": [], "confidence": "Low",
                                       "warnings": ["Human input required"]}
    result, _ = invoke(json.dumps(original), model=BlueprintContent, repair=True,
                        repaired_raw=json.dumps(repaired))
    assert result.content == repaired


def test_missing_section_cannot_be_filled_with_new_facts_by_a_syntax_repair():
    original = complete_artifact()
    original.pop("art_style_direction")
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(json.dumps(original), model=BlueprintContent, repair=True,
               repaired_raw=json.dumps(complete_artifact()))


@pytest.mark.parametrize("changed_citations", [[], ["invented-source-private"]])
def test_readable_citation_provenance_is_preserved(changed_citations):
    repaired = complete_artifact()
    repaired["summary"]["citations"] = changed_citations
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke(json.dumps(invalid_metadata_blueprint()), model=BlueprintContent, repair=True,
               repaired_raw=json.dumps(repaired))
    assert "invented-source-private" not in json.dumps(caught.value.diagnostics)


def test_json_booleans_are_not_interchangeable_with_numeric_settings():
    original = invalid_metadata_blueprint()
    original["gameplay_systems"]["content"] = {"friendly_fire": False}
    repaired = copy.deepcopy(original)
    repaired["summary"]["confidence"] = "High"
    repaired["gameplay_systems"]["content"]["friendly_fire"] = 0
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(json.dumps(original), model=BlueprintContent, repair=True, repaired_raw=json.dumps(repaired))


def test_complete_json_fence_is_readable_for_preservation_comparison():
    result, calls = invoke('```json\n' + json.dumps(invalid_metadata_blueprint()) + '\n```',
                           model=BlueprintContent, repair=True, repaired_raw=json.dumps(complete_artifact()))
    assert len(calls) == 2 and result.content == complete_artifact()


def test_duplicate_keys_make_the_original_ambiguous_even_when_repaired_output_is_valid():
    raw = json.dumps(invalid_metadata_blueprint()).replace(
        '"confidence": "not-a-confidence"', '"confidence": "High", "confidence": "not-a-confidence"')
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(raw, model=BlueprintContent, repair=True, repaired_raw=json.dumps(complete_artifact()))


def test_empty_typed_container_shape_can_be_repaired_without_adding_npcs():
    original = complete_artifact()
    original["npc_archetypes"]["content"] = {}
    repaired = copy.deepcopy(original)
    repaired["npc_archetypes"]["content"] = {"npcs": []}
    result, _ = invoke(json.dumps(original), model=BlueprintContent, repair=True,
                        repaired_raw=json.dumps(repaired))
    assert result.content == repaired


def test_invalid_npc_record_cannot_be_replaced_with_an_invented_valid_record():
    original = complete_artifact()
    original["npc_archetypes"]["content"]["npcs"][0]["name"] = None
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(json.dumps(original), model=BlueprintContent, repair=True,
               repaired_raw=json.dumps(complete_artifact()))


def test_invalid_section_scalar_cannot_be_replaced_with_new_design_facts():
    original = complete_artifact()
    original["summary"] = 3
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(json.dumps(original), model=BlueprintContent, repair=True,
               repaired_raw=json.dumps(complete_artifact()))


def misplaced_npc_metadata():
    original = complete_artifact()
    section = original["npc_archetypes"]
    npc = section["content"]["npcs"][0]
    for key in ("citations", "confidence", "warnings"):
        npc[key] = section.pop(key)
    return original


@pytest.mark.parametrize("scoped", [False, True])
def test_single_npc_section_metadata_recovers_exact_values_without_hosted_repair(scoped):
    from app.design_agent.contracts import revision_response_model
    expected = complete_artifact()
    original = misplaced_npc_metadata()
    expected["npc_archetypes"]["warnings"] = ["Private proposal requires review."]
    original["npc_archetypes"]["content"]["npcs"][0]["warnings"] = ["Private proposal requires review."]
    model = revision_response_model(["npc_archetypes"], generated=True) if scoped else BlueprintContent
    if scoped:
        original = {"npc_archetypes": original["npc_archetypes"]}
        expected = {"npc_archetypes": expected["npc_archetypes"]}
    before = copy.deepcopy(original)
    result, calls = invoke(json.dumps(original), model=model)
    assert original == before and result.content == expected
    assert len(calls) == 1 and result.metadata["repair_attempts"] == 0
    assert result.metadata["local_recovery"] and result.metadata["recovery_requires_review"]
    assert result.metadata["validation_diagnostics"][0]["local_recovery"] == {
        "kind": "misnested_single_npc_section_metadata", "moved_fields": 3,
    }
    assert "Private proposal requires review" not in json.dumps(result.metadata)


@pytest.mark.parametrize("kind", ["two_npcs", "outer_conflict", "missing_metadata", "invalid_metadata", "invalid_record", "unknown_record_field", "duplicate_key"])
def test_npc_metadata_recovery_rejects_ambiguous_or_incomplete_values(kind):
    from app.design_agent.contracts import revision_response_model
    original = misplaced_npc_metadata()
    section = original["npc_archetypes"]
    npc = section["content"]["npcs"][0]
    if kind == "two_npcs":
        section["content"]["npcs"].append(copy.deepcopy(npc))
    elif kind == "outer_conflict":
        section["confidence"] = "Low"
    elif kind == "missing_metadata":
        npc.pop("warnings")
    elif kind == "invalid_metadata":
        npc["citations"] = [17]
    elif kind == "invalid_record":
        npc["name"] = None
    elif kind == "unknown_record_field":
        npc["unrecognized_design_data"] = "Do not discard this."
    raw = json.dumps({"npc_archetypes": section})
    if kind == "duplicate_key":
        raw = raw.replace('"confidence": "High"', '"confidence": "Low", "confidence": "High"')
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(raw, model=revision_response_model(["npc_archetypes"], generated=True))


def test_generated_npc_schema_does_not_silently_drop_nested_section_metadata():
    from pydantic import ValidationError
    from app.design_agent.contracts import revision_response_model
    model = revision_response_model(["npc_archetypes"], generated=True)
    section = complete_artifact()["npc_archetypes"]
    section["content"]["npcs"][0]["warnings"] = ["Do not silently discard this warning."]
    with pytest.raises(ValidationError):
        model.model_validate({"npc_archetypes": section})


def test_model_repair_cannot_silently_discard_ambiguous_nested_metadata():
    from app.design_agent.contracts import revision_response_model
    original = complete_artifact()["npc_archetypes"]
    original["content"]["npcs"][0]["warnings"] = ["Do not discard this warning."]
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(json.dumps({"npc_archetypes": original}),
               model=revision_response_model(["npc_archetypes"], generated=True), repair=True,
               repaired_raw=json.dumps({"npc_archetypes": complete_artifact()["npc_archetypes"]}))


def test_complete_metadata_can_recover_after_a_truncation_retry_without_another_request():
    import httpx
    from app.design_agent.contracts import revision_response_model
    from app.design_agent.llm_provider import CompletionRequest, NvidiaProvider
    from test_design_agent_llm_provider import _completion
    original = misplaced_npc_metadata()
    raw = json.dumps({"npc_archetypes": original["npc_archetypes"]})
    calls = []

    def handler(request):
        calls.append(request)
        return _completion(raw[:-20] if len(calls) == 1 else raw,
                           finish_reason="length" if len(calls) == 1 else "stop")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = NvidiaProvider(base_url="https://example.invalid/v1", timeout_seconds=1,
                                  repair_enabled=True, client=client, key_reader=lambda _: "fixture-key")
        result = provider.complete(CompletionRequest(node_name="revise", messages=[],
            response_model=revision_response_model(["npc_archetypes"], generated=True)))
    assert len(calls) == 2 and result.metadata["repair_attempts"] == 0
    assert result.metadata["truncation_retries"] == 1 and result.metadata["recovery_requires_review"]
    assert result.content == {"npc_archetypes": complete_artifact()["npc_archetypes"]}


def test_recovered_revision_preserves_unselected_sections_and_stays_approval_blocked():
    from app.design_agent.grounding import assess_artifact_quality, validate_design_approval
    from app.design_agent.llm_provider import CompletionResult
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    content = complete_artifact()
    original = copy.deepcopy(content)

    class RecoveredTransport:
        def complete(self, request):
            assert "four sibling keys: content, citations, confidence, warnings" in request.messages[1]["content"]
            return CompletionResult(content={"npc_archetypes": copy.deepcopy(content["npc_archetypes"])},
                                    provider_name="nvidia", model_name="fixture",
                                    metadata={"local_recovery": True, "recovery_requires_review": True})

    result = NvidiaDesignAgentProvider(llm_provider=RecoveredTransport()).revise(
        content, [], "Preserve the profile; correct section metadata only.", ["npc_archetypes"])
    assert content == original
    assert all(result.content[key] == original[key] for key in original if key != "npc_archetypes")
    assert result.content["npc_archetypes"]["content"] == original["npc_archetypes"]["content"]
    assert result.content["npc_archetypes"]["citations"] == original["npc_archetypes"]["citations"]
    assert "Recovered output" in assess_artifact_quality(result.content)["blockers"]
    with pytest.raises(ValueError, match="Recovered output|Integration readiness"):
        validate_design_approval(result.content, [], {"verdict": "ready_for_review", "findings": []})
