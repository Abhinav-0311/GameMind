"""Non-Latin dialogue must retain the same proposal/source boundary as English."""
import pytest

from app.design_agent.grounding import _normalise_for_quote_match, validate_generated_blueprint
from test_revision_completeness_guards import complete_artifact


LINES = [
    "लिंक खोलने से पहले पता जाँचो।",
    "先检查链接，再打开它。",
    "リンクを開く前に確認してください。",
    "افحص الرابط قبل فتحه.",
    "링크를 열기 전에 확인하세요.",
]
SOURCE_ID = "11111111-1111-1111-1111-111111111111"


def design(line, *, reuse):
    content = complete_artifact(SOURCE_ID)
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_hooks"] = [line]
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest.update({"objective": "Inspect the relay.", "objectives": ["Inspect the relay."],
                  "failure_states": [], "dialogue_hooks": [line]})
    source = "Mira guides the player. Inspect the relay."
    if reuse:
        source += " " + line
    evidence = [{"chunk_id": SOURCE_ID, "content": source,
                 "matched_sections": ["npc_archetypes", "quest_hooks"]}]
    return validate_generated_blueprint(content, evidence)


@pytest.mark.parametrize("line", LINES)
def test_new_non_latin_npc_and_quest_lines_are_marked_as_creative_proposals(line):
    result = design(line, reuse=False)
    npc = result["npc_archetypes"]["content"]["npcs"][0]
    quest = result["quest_hooks"]["content"]["quests"][0]
    assert any("Generated dialogue hooks" in assumption for assumption in npc["assumptions"])
    assert any("dialogue hooks" in assumption for assumption in quest["assumptions"])
    assert not any("Reused source dialogue:" in warning for warning in result["npc_archetypes"]["warnings"])


@pytest.mark.parametrize("line", LINES)
def test_real_non_latin_source_lines_remain_visible_as_reuse_not_fresh_generation(line):
    result = design(line, reuse=True)
    npc = result["npc_archetypes"]["content"]["npcs"][0]
    assert npc["dialogue_hooks"] == [line]
    assert not any("Generated dialogue hooks" in assumption for assumption in npc["assumptions"])
    assert any("1 source-text hook(s)" in warning for warning in result["npc_archetypes"]["warnings"])


def test_unicode_marks_are_preserved_so_different_words_do_not_collapse():
    assert _normalise_for_quote_match("कला") != _normalise_for_quote_match("कल")
    assert _normalise_for_quote_match("है") != _normalise_for_quote_match("ह")


def test_unicode_normalization_preserves_words_and_equivalent_typography():
    assert _normalise_for_quote_match("Café") == _normalise_for_quote_match("Cafe\u0301")
    assert _normalise_for_quote_match("Don't open it.") == _normalise_for_quote_match("Don’t open it!")
