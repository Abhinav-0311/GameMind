"""Regressions from the real CyberRakshak draft; no hosted calls."""
import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, build_section_queries
from app.design_agent.grounding import review_targets, validate_structured_revision, validate_generated_blueprint
from app.design_agent.llm_provider import CompletionResult
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from app.design_agent.provider import MockDesignAgentProvider
from app.design_agent.schemas import DesignAgentReviewRequest
from app.services.rag_service import RAGService


def test_compaction_retains_early_level_and_character_passages_without_extra_cuts(monkeypatch):
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_ITEMS", 27)
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 1200)
    evidence = [
        {"chunk_id": f"broad-{i}", "content": "Broad scope. " * 70,
         "matched_sections": ["summary", "gameplay_systems", "unity_runtime_preview"],
         "similarity": 0.9, "chunk_index": i}
        for i in range(10)
    ]
    evidence.extend([
        {"chunk_id": "early-level", "content": "Level plan. " * 60 + "Password Vault follows Training Sandbox.",
         "matched_sections": ["level_design_suggestions", "quest_hooks"], "similarity": 0.4},
        {"chunk_id": "patch", "content": "Companion context. " * 35 + "PATCH is funny and warning-based, not teacher-like.",
         "matched_sections": ["npc_archetypes"], "similarity": 0.3},
    ])
    original = copy.deepcopy(evidence)
    selected = NvidiaDesignAgentProvider._compact_evidence(evidence)
    by_id = {item["chunk_id"]: item for item in selected}
    assert by_id["early-level"]["content"] == evidence[-2]["content"]
    assert by_id["patch"]["content"] == evidence[-1]["content"]
    assert not by_id["patch"]["content_truncated"]
    assert evidence == original


def test_small_configured_budget_keeps_relevant_complete_tail(monkeypatch):
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_ITEMS", 1)
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 180)
    text = "General unrelated context. " * 30 + "PATCH provides funny scripted dialogue warnings as a companion support guide."
    evidence = [{"chunk_id": "patch", "content": text, "matched_sections": ["npc_archetypes"]}]
    item = NvidiaDesignAgentProvider._compact_evidence(evidence)[0]
    assert "PATCH provides funny" in item["content"]
    assert len(item["content"]) <= 180
    assert item["content"].endswith(".")
    assert item["content"] == text[item["excerpt_start"]:item["excerpt_end"]]


def test_section_queries_route_character_voice_and_early_missions(monkeypatch):
    # Exact short passages from the bundled GDD, isolated from persistent Chroma.
    passages = [
        "PATCH is Adi's AI support tool. PATCH provides hints, warnings, mission reactions, "
        "and short cybersecurity explanations. PATCH must be funny, helpful, and warning-based rather than teacher-like.",
        "## 9. Story mode level plan\n### Level 1: Training Sandbox\nFocus: basic movement, traversal, loadout, combat, and mission structure.\n"
        "### Level 2: Password Vault\nFocus: passwords and authentication.",
        "Evaluate the project using awareness scores, wrong-interaction count, threat-recognition accuracy, and surveys.",
        "Shared systems include the cyber-threat database, scoring rules, player profile, leaderboard logic, UI style, and PATCH dialogue content.",
    ]

    class OfflineCollection:
        def count(self):
            return len(passages)

        def query(self, **kwargs):
            raise RuntimeError("Cannot return the results in a contigious 2D array")

        def get(self, *, where, include):
            assert where == {"$and": [{"game_project_id": "fixture"}, {"document_id": {"$in": ["gdd"]}}]}
            return {"ids": [f"source-{i}" for i in range(len(passages))], "documents": passages,
                    "metadatas": [{"chunk_index": i, "document_id": "gdd"} for i in range(len(passages))]}

    rag = object.__new__(RAGService)
    rag.collection = OfflineCollection()
    retrieved = rag.query_lore_sections(build_section_queries("", ""), game_project_id="fixture", document_ids=["gdd"])
    by_id = {item["chunk_id"]: item for item in retrieved}
    assert "npc_archetypes" in by_id["source-0"]["matched_sections"]
    assert "quest_hooks" in by_id["source-1"]["matched_sections"]
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_ITEMS", 10)
    monkeypatch.setattr(NvidiaDesignAgentProvider, "_MAX_EVIDENCE_CHARS_PER_ITEM", 600)
    npc = NvidiaDesignAgentProvider._compact_evidence(retrieved, ["npc_archetypes"])
    quests = NvidiaDesignAgentProvider._compact_evidence(retrieved, ["quest_hooks"])
    assert any("warning-based rather than teacher-like" in item["content"] for item in npc)
    assert any("Training Sandbox" in item["content"] and "Password Vault" in item["content"] for item in quests)


@pytest.mark.parametrize("filename,queries", [
    ("cyberrakshak_gdd.md", {
        "summary": "PATCH NPC profile three new short spoken warnings suspicious link executable file literal firewall Firewall Fortress quest safe route block malicious path player action Event State Check failure event restart transition",
        "level_design_suggestions": "Firewall Fortress quest safe route block malicious path player action Event State Check",
        "quest_hooks": "Firewall Fortress quest safe route block malicious path player action Event State Check",
    }),
    ("sample_gdd_frostpeak.md", {
        "summary": "Eldrin NPC quest hook Ash Pass guard flag completion requirements",
        "level_design_suggestions": "Ash Pass layout guard positions flag locations player path",
        "quest_hooks": "Eldrin Hook 1 mechanics quest initiation conditions",
    }),
])
def test_saved_planner_queries_retain_source_overview_and_quest_evidence(filename, queries):
    """Replay the failed QA queries with real chunking/embeddings, no DB or inference."""
    rag = object.__new__(RAGService)
    source = (Path(__file__).resolve().parents[1] / "docs" / "demo" / filename).read_text(encoding="utf-8")
    passages = rag.chunk_text(source)
    vectors = rag._local_embeddings(passages)
    calls = []

    class OfflineCollection:
        def count(self):
            return len(passages)

        def query(self, *, query_texts, query_embeddings, n_results, where):
            assert where == {"$and": [
                {"game_project_id": "fixture"}, {"document_id": {"$in": ["selected-gdd"]}},
            ]}
            calls.append(query_texts)
            rows = {key: [] for key in ("ids", "distances", "documents", "metadatas")}
            for query in query_embeddings:
                scores = [sum(a * b for a, b in zip(query, vector)) for vector in vectors]
                indices = sorted(range(len(passages)), key=lambda i: (-scores[i], i))[:n_results]
                rows["ids"].append([f"source-{i}" for i in indices])
                rows["distances"].append([1 - scores[i] for i in indices])
                rows["documents"].append([passages[i] for i in indices])
                rows["metadatas"].append([{
                    "chunk_index": i, "document_id": "selected-gdd", "game_project_id": "fixture",
                } for i in indices])
            return rows

    rag.collection = OfflineCollection()
    original_queries = copy.deepcopy(queries)
    evidence = rag.query_lore_sections(queries, game_project_id="fixture", document_ids=["selected-gdd"])
    assert queries == original_queries
    assert len(calls) == 1 and len(calls[0]) <= 2 * len(queries)
    assert all(query in calls[0] for query in queries.values())
    assert "summary" in next(item for item in evidence if item["chunk_index"] == 0)["matched_sections"]
    compacted = NvidiaDesignAgentProvider._compact_evidence(evidence, list(queries))
    assert any(item["chunk_index"] == 0 and "summary" in item["matched_sections"] for item in compacted)
    if filename == "cyberrakshak_gdd.md":
        assert any("### Level 5: Firewall Fortress" in item["content"]
                   and "quest_hooks" in item["matched_sections"] for item in compacted)
        for number in range(1, 11):
            assert any(f"### Level {number}:" in item["content"]
                       and "level_design_suggestions" in item["matched_sections"] for item in compacted)
    else:
        assert any("100 gold and 250 XP" in item["content"]
                   and "quest_hooks" in item["matched_sections"] for item in compacted)


def test_legacy_negated_mentions_do_not_expand_revision_scope():
    assert review_targets(
        "Revise only npc_archetypes. Preserve every other section exactly; "
        "this revision does not authorize quest or story changes."
    ) == ["npc_archetypes"]


def test_public_rejection_requires_valid_explicit_scope():
    with pytest.raises(ValidationError):
        DesignAgentReviewRequest(decision="reject", reason="Improve the dialogue.")
    with pytest.raises(ValidationError):
        DesignAgentReviewRequest(decision="reject", reason="Improve.", target_sections=[])
    with pytest.raises(ValidationError):
        DesignAgentReviewRequest(decision="reject", reason="Improve.", target_sections=["unknown"])
    request = DesignAgentReviewRequest(
        decision="reject", reason="Do not change quests or story.",
        target_sections=["npc_archetypes"],
    )
    assert request.target_sections == ["npc_archetypes"]
    assert DesignAgentReviewRequest(decision="approve").decision == "approve"


def test_hosted_revision_sends_only_selected_section_and_evidence():
    evidence = [
        {"chunk_id": "patch", "content": "PATCH provides humorous warning hooks.",
         "matched_sections": ["npc_archetypes"], "similarity": 0.9},
        {"chunk_id": "quest", "content": "UNRELATED_QUEST_PAYLOAD",
         "matched_sections": ["quest_hooks"], "similarity": 0.95},
    ]
    before = MockDesignAgentProvider().generate({"objective": "Build a game"}, evidence).content
    before["quest_hooks"]["content"]["quests"] = []
    before["summary"]["content"] = {"description": "UNRELATED_SUMMARY_PAYLOAD"}
    section = {"content": {"npcs": []}, "citations": ["patch"],
               "confidence": "Medium", "warnings": ["Needs a designer decision."]}

    class Capture:
        def complete(self, request):
            self.request = request
            return CompletionResult(
                content=request.response_model.model_validate({"npc_archetypes": section}).model_dump(),
                provider_name="nvidia", model_name="test-model",
            )

    capture = Capture()
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    original = copy.deepcopy(before)
    result = provider.revise(before, evidence, "Do not change quests or story.",
                             target_sections=["npc_archetypes"])
    prompt = capture.request.messages[1]["content"]
    assert "UNRELATED_SUMMARY_PAYLOAD" not in prompt
    assert "UNRELATED_QUEST_PAYLOAD" not in prompt
    assert set(capture.request.response_model.model_fields) == {"npc_archetypes"}
    assert capture.request.response_model.model_json_schema()["additionalProperties"] is False
    for name in BLUEPRINT_SECTION_KEYS:
        assert result.content[name] == (section if name == "npc_archetypes" else before[name])
    assert before == original
    assert result.metadata["revision_targets"] == ["npc_archetypes"]
    assert result.metadata["evidence_payload"]["chunk_ids"] == ["patch"]


def test_explicit_scope_validation_rejects_drift_despite_prose_mentions():
    before = MockDesignAgentProvider().generate({"objective": "Build a game"}, []).content
    after = copy.deepcopy(before)
    after["summary"]["content"] = {"overview": "Corrected summary"}
    after["quest_hooks"]["content"]["quests"] = []
    assert validate_structured_revision(before, after, "Do not change quest or story.",
                                        target_sections=["summary"]) == "summary"
    after["narrative_direction"]["content"] = {"story": "Unrelated rewrite"}
    with pytest.raises(ValueError, match="changed unrelated sections"):
        validate_structured_revision(before, after, "Do not change quest or story.",
                                     target_sections=["summary"])


def test_trigger_identifiers_are_not_accepted_as_spoken_dialogue():
    evidence = [{"chunk_id": "patch", "content": "PATCH provides warnings.", "matched_sections": ["npc_archetypes"]}]
    content = MockDesignAgentProvider().generate({"objective": "Build a game"}, evidence).content
    content["npc_archetypes"]["content"]["npcs"] = [{
        "name": "PATCH", "archetype": "Companion", "dialogue_style": "Funny warnings",
        "source_chunk_ids": ["patch"], "dialogue_hooks": ["suspicious_link_wrong_interaction", "firewall_first_encounter"],
    }]
    validated = validate_generated_blueprint(content, evidence)
    assert validated["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] == []
    assert any("actual spoken lines" in warning for warning in validated["npc_archetypes"]["warnings"])
    with pytest.raises(ValueError, match="no cited dialogue hook"):
        validate_generated_blueprint(content, evidence, require_actionable=True, actionable_sections={"npc_archetypes"})
