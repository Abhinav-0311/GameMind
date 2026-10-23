"""Synthetic fixtures only: the failed live model text was not retained."""
import copy
import json
import traceback

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.design_agent.contracts import NPCDialogueRevisionOutput
from app.design_agent.grounding import assess_artifact_quality, validate_generated_blueprint
from app.design_agent.llm_provider import (
    CompletionRequest, NvidiaProvider, NvidiaStructuredOutputError,
)
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from app.design_agent.provider import MockDesignAgentProvider
from test_design_agent_llm_provider import _completion


def fixture():
    return {"npc_archetypes": {"patches": [{
        "name": "Mira", "source_chunk_ids": ["fixture-source"], "assumptions": [],
        "dialogue_triggers": [{
            "trigger": "relay_approach", "situation": "Approach the sparking relay",
            "text": 'The sign says {stand back}; read it. Then say "clear".',
            "repeat_policy": "Once per encounter; reset after leaving.",
        }],
    }]}}


def invoke(raw, *, model=NPCDialogueRevisionOutput, finish_reason="stop", repair=False, repaired_raw=None):
    requests = []

    def handler(request):
        requests.append(request)
        return _completion(raw if len(requests) == 1 else repaired_raw, finish_reason=finish_reason)

    provider = NvidiaProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1,
        repair_enabled=repair,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda _: "credential-never-log", sleep=lambda _: None,
    )
    result = provider.complete(CompletionRequest(
        node_name="revise", messages=[{"role": "user", "content": "private-source-never-log"}],
        response_model=model,
    ))
    return result, requests


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_missing_outer_closers_recover_without_changing_design_data_or_calling_repair(count):
    original = fixture()
    raw = json.dumps(original, separators=(",", ":"))[:-count]
    result, requests = invoke(raw)
    assert result.content == original
    assert len(requests) == 1 and result.metadata["repair_attempts"] == 0
    assert result.metadata["local_recovery"] is True
    assert result.metadata["repaired"] is True
    assert result.metadata["recovery_requires_review"] is True
    record = result.metadata["validation_diagnostics"][0]
    assert record["failure_kind"] == "json_syntax"
    assert record["local_recovery"] == {"kind": "missing_closing_delimiters", "appended_closers": count}
    assert record["json_error"]["at_end_of_candidate"] is True
    rendered = json.dumps(result.metadata)
    for secret in ("credential-never-log", "private-source-never-log", "stand back", raw):
        assert secret not in rendered


def test_valid_output_is_not_marked_recovered():
    result, requests = invoke(json.dumps(fixture()))
    assert len(requests) == 1
    assert result.metadata["local_recovery"] is False
    assert result.metadata["recovery_requires_review"] is False
    assert result.metadata["repaired"] is False


def test_parser_preserves_full_eof_candidate_including_closed_arrays():
    raw = json.dumps(fixture())[:-2]
    assert raw.endswith("]")
    with pytest.raises(json.JSONDecodeError) as caught:
        NvidiaProvider._extract_json(raw)
    assert caught.value.doc == raw
    assert caught.value.pos == len(raw)


def test_complete_json_fence_allows_only_inner_missing_closers():
    raw = '```json\n' + json.dumps(fixture())[:-1] + '\n```'
    result, requests = invoke(raw)
    assert result.content == fixture() and len(requests) == 1
    assert result.metadata["local_recovery"] is True


@pytest.mark.parametrize("raw", [
    '{"npc_archetypes":{"patches":[{"name":"Mi',
    '{"npc_archetypes":{"patches":[{"name":"Mira\\',
    '{"npc_archetypes":{"patches":',
    '{"npc_archetypes":{"patches":[{},',
    '{"npc_archetypes":{"patches":[}',
    '{"npc_archetypes":{"patches":[{}',
    '{"npc_archetypes":{"patches":[{"name":"Mira","source_chunk_ids":["s"]}',
    'Result:\n' + json.dumps(fixture())[:-1],
    '```json\n' + json.dumps(fixture())[:-1],
    json.dumps(fixture())[:-1] + ' extra-data',
    json.dumps(fixture()).replace('"name": "Mira"', '"name": "Mira", "name": "Mira"')[:-1],
    json.dumps(fixture()).replace('"assumptions": []', '"assumptions": [], "unknown": "private-value"')[:-1],
    json.dumps(fixture())[:-1] + ',',
    '{"npc_archetypes":' + '[' * 80 + '{}',
])
def test_ambiguous_or_incomplete_content_is_not_locally_recovered(raw):
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke(raw)
    assert caught.value.attempts == 1
    rendered = json.dumps(caught.value.diagnostics) + ''.join(traceback.format_exception(caught.value))
    assert "credential-never-log" not in rendered and "private-value" not in rendered


@pytest.mark.parametrize("finish", [None, "unknown", "content_filter", "tool_calls"])
def test_only_normal_stop_is_eligible_for_recovery(finish):
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(json.dumps(fixture())[:-1], finish_reason=finish)


def test_truncation_retry_output_is_not_eligible_for_local_recovery():
    raw = json.dumps(fixture())[:-1]
    replies = iter([_completion(raw, finish_reason="length"), _completion(raw, finish_reason="stop")])
    calls = []
    provider = NvidiaProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=False,
        client=httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(1) or next(replies))),
        key_reader=lambda _: "credential-never-log", sleep=lambda _: None,
    )
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=NPCDialogueRevisionOutput))
    assert calls == [1, 1] and caught.value.attempts == 2
    assert "local_recovery" not in json.dumps(caught.value.diagnostics)


def test_other_response_contracts_do_not_gain_implicit_recovery():
    class OtherContract(BaseModel):
        model_config = ConfigDict(extra="forbid")
        values: list[str]

    with pytest.raises(NvidiaStructuredOutputError):
        invoke('{"values":["complete"]', model=OtherContract)


def test_one_model_repair_can_also_use_guarded_local_closure():
    result, requests = invoke('{"npc_archetypes":', repair=True, repaired_raw=json.dumps(fixture())[:-1])
    assert len(requests) == 2
    assert result.content == fixture() and result.metadata["repair_attempts"] == 1
    assert result.metadata["local_recovery"] is True
    assert result.metadata["validation_diagnostics"][-1]["stage"] == "repair"


def test_safe_structural_diagnostics_distinguish_unclosed_string_and_containers():
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke('{"npc_archetypes":{"patches":[{"name":"private-value')
    record = caught.value.diagnostics["completions"][0]
    assert record["json_structure"]["inside_string"] is True
    assert record["json_structure"]["unclosed_objects"] == 3
    assert record["json_structure"]["unclosed_arrays"] == 1
    assert "private-value" not in json.dumps(record)


def test_recovered_patch_has_visible_warning_and_remains_a_review_draft():
    evidence = [{"chunk_id": "fixture-source", "content": "Mira is a scout at the sparking relay.",
                 "matched_sections": ["npc_archetypes"]}]
    before = MockDesignAgentProvider().generate({"objective": "Build Frostpeak"}, evidence).content
    before["npc_archetypes"]["content"]["npcs"] = [{
        "name": "Mira", "archetype": "Scout", "dialogue_style": "Dry wit",
        "source_chunk_ids": ["fixture-source"], "dialogue_hooks": ["Stay alert."],
    }]
    original = copy.deepcopy(before)
    raw = json.dumps(fixture())[:-1]
    calls = []
    transport = NvidiaProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=False,
        client=httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(1) or _completion(raw))),
        key_reader=lambda _: "credential-never-log",
    )
    result = NvidiaDesignAgentProvider(llm_provider=transport).revise(
        before, evidence, "Fix Mira's dialogue.", ["npc_archetypes"])
    assert calls == [1] and before == original
    section = result.content["npc_archetypes"]
    assert any("closing-delimiter recovery" in warning for warning in section["warnings"])
    npc = section["content"]["npcs"][0]
    assert any("closing-delimiter recovery" in item for item in npc["assumptions"])
    assert not assess_artifact_quality(validate_generated_blueprint(result.content, evidence))["passed"]
