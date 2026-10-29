import sys
import copy

import httpx
import pytest

from app.design_agent.llm_provider import CompletionRequest, NvidiaTruncatedOutputError
from tools.probe_dialogue_json import (
    SingleNPCDialogue, SingleCallProvider, ThreeSituationDialogue, main,
    select_warning_evidence, validated_probe_candidate,
)
from test_design_agent_llm_provider import _completion
from test_dialogue_trigger_alignment import artifact, LINES


@pytest.mark.parametrize("arguments", [
    ["--project-id", "qa-cyberrakshak-test", "--run-id", "56218f49-d469-4057-aad6-a5c891031dee"],
    ["--hosted-consent", "--project-id", "real-game", "--run-id", "56218f49-d469-4057-aad6-a5c891031dee"],
])
def test_probe_requires_consent_and_qa_scope_before_database_access(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["probe", *arguments])
    monkeypatch.setattr("tools.probe_dialogue_json.SessionLocal", lambda: pytest.fail("Must not access database"))
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


def test_probe_has_no_hidden_truncation_retry():
    calls = []

    def handler(request):
        calls.append(1)
        return _completion("unfinished", finish_reason="length")

    provider = SingleCallProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=False,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda name: "test-only-credential",
    )
    with pytest.raises(NvidiaTruncatedOutputError):
        provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=SingleNPCDialogue))
    assert len(calls) == 1


def pack_fixture():
    evidence = [{"chunk_id": "patch", "content": "PATCH examples:\n" + "\n".join(f'"{line}"' for line in LINES),
                 "matched_sections": ["npc_archetypes"]}]
    npc = artifact()["npc_archetypes"]["content"]["npcs"][0]
    content = {"name": "PATCH", "source_chunk_ids": ["patch"],
               **dict(zip(("link", "file", "firewall"), npc["dialogue_triggers"]))}
    return evidence, content


def test_three_situation_evidence_preserves_exact_source_windows_and_order():
    evidence, _ = pack_fixture()
    original = copy.deepcopy(evidence)
    selected = select_warning_evidence(evidence, ("link", "file", "firewall"))
    assert [item["probe_situation"] for item in selected] == ["link", "file", "firewall"]
    assert [item["content"] for item in selected] == LINES
    for item in selected:
        assert item["content"] == evidence[0]["content"][item["excerpt_start"]:item["excerpt_end"]]
    assert evidence == original


@pytest.mark.parametrize("fault", ["missing", "unrouted"])
def test_missing_or_unrouted_quote_blocks_pack_preparation(fault):
    evidence, _ = pack_fixture()
    if fault == "missing":
        evidence[0]["content"] = f'"{LINES[0]}"'
    else:
        evidence[0]["matched_sections"] = ["quest_hooks"]
    with pytest.raises(ValueError, match="Missing NPC-routed"):
        select_warning_evidence(evidence, ("link", "file", "firewall"))


def test_named_pack_survives_production_grounding_without_mutating_input():
    evidence, content = pack_fixture()
    typed = ThreeSituationDialogue.model_validate(content).model_dump()
    original = artifact()
    before = copy.deepcopy(original)
    selected = select_warning_evidence(evidence, ("link", "file", "firewall"))
    result = validated_probe_candidate(original, typed, selected, evidence, True)
    npc = result["npc_archetypes"]["content"]["npcs"][0]
    assert npc["dialogue_hooks"] == LINES
    assert len(npc["dialogue_triggers"]) == 3
    assert npc["assumptions"], "Proposed triggers must not auto-certify runtime readiness"
    assert original == before


def test_swapped_named_source_lines_are_rejected_before_use():
    evidence, content = pack_fixture()
    content["link"]["text"], content["file"]["text"] = content["file"]["text"], content["link"]["text"]
    with pytest.raises(ValueError, match="named situation"):
        validated_probe_candidate(artifact(), content,
                                  select_warning_evidence(evidence, ("link", "file", "firewall")), evidence, True)


def test_pack_cannot_cite_an_unselected_source():
    evidence, content = pack_fixture()
    content["source_chunk_ids"] = ["other-source"]
    with pytest.raises(ValueError, match="outside the frozen selected"):
        validated_probe_candidate(artifact(), content,
                                  select_warning_evidence(evidence, ("link", "file", "firewall")), evidence, True)
