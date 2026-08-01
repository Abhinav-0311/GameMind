import copy

import pytest

from app.design_agent.grounding import (
    ground_blueprint_citations,
    validate_structured_revision,
)
from app.design_agent.provider import MockDesignAgentProvider
from app.services.rag_service import RAGService


CYBERRAKSHAK_CORE_SOURCE = """# CyberRakshak: The Ethical Hacker

## Project profile
CyberRakshak is a story-driven low-poly 3D cyber-infiltration platformer.

## 5. Main characters
### Adi
Adi is the player character and a beginner ethical hacker.

### Jay
Jay is Adi's supervisor and secretly uses him to enter real systems.

### PATCH
PATCH is Adi's funny, warning-based AI support tool.

## 6. Core gameplay loop
1. Enter a mission.
2. Identify the target and environment.
3. Choose stealth, bold, puzzle, or speed.
4. Retrieve evidence, expose the vulnerability, and escape.

## 9. Story mode level plan
### Level 1: Training Sandbox
Focus: basic movement, traversal, loadout, combat, and mission structure.
### Level 2: Password Vault
Focus: passwords and authentication.
### Level 3: Phishing Office
Focus: phishing and fake websites.
### Level 4: Malware Warehouse
Focus: malware and suspicious downloads.
### Level 5: Firewall Fortress
Focus: firewalls and access control.
### Level 6: QR Market
Focus: QR scams and digital-payment fraud.
### Level 7: Social Engineering Plaza
Focus: manipulation, impersonation, and trust.
### Level 8: Ransomware Ruins
Focus: ransomware, backups, and locked data.
### Level 9: The Reveal
Focus: Adi learns that Jay used him to enter real systems.
### Level 10: Hunt Jay
Focus: Adi works with cyber police to track Jay and expose him.
"""


def _cyber_evidence():
    return [
        {
            "chunk_id": "11111111-1111-1111-1111-111111111111",
            "content": CYBERRAKSHAK_CORE_SOURCE,
            "document_id": "22222222-2222-2222-2222-222222222222",
            "title": "cyberrakshak_gdd.md",
            "chunk_index": 0,
            "game_project_id": "cyberrakshak",
            "similarity": 0.92,
            "confidence": "High",
            "matched_sections": [
                "summary",
                "narrative_direction",
                "npc_archetypes",
                "level_design_suggestions",
                "gameplay_systems",
                "quest_hooks",
                "unity_runtime_preview",
            ],
            "section_similarities": {
                "summary": 0.92,
                "narrative_direction": 0.9,
                "npc_archetypes": 0.94,
                "level_design_suggestions": 0.98,
                "gameplay_systems": 0.9,
                "quest_hooks": 0.86,
                "unity_runtime_preview": 0.81,
            },
        }
    ]


def test_mock_generation_extracts_all_ten_cyberrakshak_levels():
    provider = MockDesignAgentProvider()
    result = provider.generate({"objective": "Build CyberRakshak"}, _cyber_evidence())
    content = ground_blueprint_citations(result.content, _cyber_evidence())

    levels = content["level_design_suggestions"]["content"]["levels"]
    assert len(levels) == 10
    assert levels[0]["title"] == "Training Sandbox"
    assert levels[-1] == {
        "number": 10,
        "title": "Hunt Jay",
        "focus": "Adi works with cyber police to track Jay and expose him.",
    }
    assert content["level_design_suggestions"]["citations"] == [
        "11111111-1111-1111-1111-111111111111"
    ]


def test_grounding_filters_cross_section_citations():
    evidence = _cyber_evidence()
    artifact = MockDesignAgentProvider().generate(
        {"objective": "Build CyberRakshak"},
        evidence,
    ).content
    artifact["art_style_direction"]["citations"] = [evidence[0]["chunk_id"]]

    grounded = ground_blueprint_citations(artifact, evidence)

    assert grounded["art_style_direction"]["citations"] == []
    assert grounded["art_style_direction"]["confidence"] == "Low"
    assert any(
        "not retrieved for this section" in warning
        for warning in grounded["art_style_direction"]["warnings"]
    )


def test_revision_contract_rejects_no_op_and_unrelated_drift():
    evidence = _cyber_evidence()
    before = MockDesignAgentProvider().generate(
        {"objective": "Build CyberRakshak"},
        evidence,
    ).content

    with pytest.raises(ValueError, match="did not materially change"):
        validate_structured_revision(
            before,
            copy.deepcopy(before),
            "Correct the level design.",
        )

    valid_revision = copy.deepcopy(before)
    valid_revision["level_design_suggestions"]["content"]["levels"][0][
        "focus"
    ] = "Teach movement before introducing combat."
    assert validate_structured_revision(
        before,
        valid_revision,
        "Correct the level design.",
    ) == "level_design_suggestions"

    invalid_revision = copy.deepcopy(valid_revision)
    invalid_revision["summary"]["content"]["description"] = "Unrelated rewrite"
    with pytest.raises(ValueError, match="changed unrelated sections"):
        validate_structured_revision(
            before,
            invalid_revision,
            "Correct the level design.",
        )


class _BatchCollection:
    def __init__(self):
        self.calls = 0

    def count(self):
        return 3

    def query(self, *, query_texts, n_results, where, **_kwargs):
        self.calls += 1
        assert query_texts == ["story evidence", "level evidence"]
        assert n_results == 2
        assert where == {
            "$and": [
                {"game_project_id": "cyberrakshak"},
                {"document_id": {"$in": ["doc-1"]}},
            ]
        }
        return {
            "ids": [["shared", "story"], ["shared", "levels"]],
            "distances": [[0.2, 0.3], [0.1, 0.25]],
            "documents": [["Shared", "Story"], ["Shared", "Levels"]],
            "metadatas": [
                [
                    {"document_id": "doc-1", "title": "GDD", "chunk_index": 0},
                    {"document_id": "doc-1", "title": "GDD", "chunk_index": 1},
                ],
                [
                    {"document_id": "doc-1", "title": "GDD", "chunk_index": 0},
                    {"document_id": "doc-1", "title": "GDD", "chunk_index": 2},
                ],
            ],
        }


def test_section_retrieval_is_one_batched_call_with_provenance():
    rag = object.__new__(RAGService)
    rag.collection = _BatchCollection()
    rag._vector_arguments = lambda _texts, _key: {}

    results = rag.query_lore_sections(
        {"narrative_direction": "story evidence", "level_design_suggestions": "level evidence"},
        limit_per_section=2,
        game_project_id="cyberrakshak",
        document_ids=["doc-1"],
    )

    assert rag.collection.calls == 1
    assert len(results) == 3
    shared = next(item for item in results if item["chunk_id"] == "shared")
    assert shared["similarity"] == 0.9
    assert shared["matched_sections"] == [
        "narrative_direction",
        "level_design_suggestions",
    ]
    assert shared["section_similarities"] == {
        "narrative_direction": 0.8,
        "level_design_suggestions": 0.9,
    }
