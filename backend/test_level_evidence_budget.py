"""Compaction must not silently erase a source-defined level sequence."""
import copy

import pytest

from app.design_agent.llm_provider import CompletionResult, NvidiaProviderError
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from test_revision_completeness_guards import complete_artifact


class Capture:
    def __init__(self):
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        content = ({"verdict": "needs_revision", "findings": [], "summary": "Needs review."}
                   if request.node_name == "critique" else complete_artifact())
        return CompletionResult(content=content, provider_name="nvidia", model_name="fixture")


def level_evidence():
    return [{
        "chunk_id": "source-private-id", "document_id": "doc", "chunk_index": 0,
        "matched_sections": ["level_design_suggestions", "quest_hooks"], "similarity": 0.9,
        "content": "\n\n".join(
            f"### Level {index}: private-source-title-{index}\n\n"
            "Focus: restore access, inspect evidence and protect the relay."
            for index in range(1, 7)
        ),
    }]


def call(provider, method, evidence):
    if method == "generate":
        return provider.generate({"objective": "Build a design."}, evidence)
    if method == "critique":
        return provider.critique(complete_artifact(), evidence)
    return provider.revise(complete_artifact(), evidence, "Correct the level sequence.",
                           target_sections=["level_design_suggestions"])


@pytest.mark.parametrize("method", ["generate", "critique", "revise"])
def test_known_level_loss_is_rejected_before_any_hosted_completion(monkeypatch, method):
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 250)
    capture = Capture()
    with pytest.raises(NvidiaProviderError) as caught:
        call(NvidiaDesignAgentProvider(llm_provider=capture), method, level_evidence())
    assert capture.requests == []
    assert caught.value.code == "evidence_payload_incomplete"
    assert caught.value.attempts == 0 and not caught.value.retryable
    assert caught.value.diagnostics["source_level_headings"] == 6
    assert caught.value.diagnostics["omitted_level_headings"] > 0
    assert "private-source" not in str(caught.value) + str(caught.value.diagnostics)


@pytest.mark.parametrize("method", ["generate", "critique", "revise"])
def test_complete_source_sequence_still_reaches_the_normal_provider(monkeypatch, method):
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 1200)
    capture = Capture()
    call(NvidiaDesignAgentProvider(llm_provider=capture), method, level_evidence())
    assert len(capture.requests) == 1


def test_focused_npc_revision_is_not_blocked_by_unrelated_level_context(monkeypatch):
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 250)
    capture = Capture()
    evidence = [*level_evidence(), {"chunk_id": "npc-context", "matched_sections": ["npc_archetypes"],
                                  "content": "The scout warns the player about the relay."}]
    NvidiaDesignAgentProvider(llm_provider=capture).revise(
        complete_artifact(), evidence, "Improve NPC notes.", target_sections=["npc_archetypes"])
    assert len(capture.requests) == 1


def test_duplicate_heading_retained_in_another_chunk_is_not_missing(monkeypatch):
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 250)
    evidence = level_evidence()
    for index, content in enumerate(evidence[0]["content"].split("\n\n### "), start=1):
        evidence.append({**copy.deepcopy(evidence[0]), "chunk_id": f"piece-{index}",
                         "chunk_index": index, "content": content if index == 1 else "### " + content})
    capture = Capture()
    call(NvidiaDesignAgentProvider(llm_provider=capture), "generate", evidence)
    assert len(capture.requests) == 1


def test_same_heading_in_another_document_cannot_fill_a_source_gap():
    original = level_evidence()
    other_document = [{**original[0], "document_id": "other-doc"}]
    with pytest.raises(NvidiaProviderError) as caught:
        NvidiaDesignAgentProvider._ensure_level_coverage(
            original, other_document, ["level_design_suggestions"])
    assert caught.value.diagnostics["omitted_level_headings"] == 6


def test_plain_text_and_unrelated_level_word_are_not_invented_outline_requirements():
    evidence = [{"matched_sections": ["level_design_suggestions"],
                 "content": "## Level of confidence\nA numbered list may describe platforming skills."}]
    NvidiaDesignAgentProvider._ensure_level_coverage(evidence, [], ["level_design_suggestions"])


def test_item_budget_loss_is_checked_even_without_character_truncation(monkeypatch):
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_ITEMS", 1)
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 1200)
    evidence = level_evidence()
    evidence.append({**copy.deepcopy(evidence[0]), "chunk_id": "last-level", "chunk_index": 1,
                     "content": "### Level 7: Last relay\nProtect the backup."})
    capture = Capture()
    with pytest.raises(NvidiaProviderError) as caught:
        call(NvidiaDesignAgentProvider(llm_provider=capture), "generate", evidence)
    assert capture.requests == [] and caught.value.diagnostics["omitted_level_headings"] == 1
