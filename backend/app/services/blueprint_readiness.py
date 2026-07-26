import re
from typing import Any, Dict, List

from app.models.blueprint import GameBlueprint


class BlueprintReadinessService:
    """Assess whether a blueprint is coherent enough to approve or materialize."""

    REQUIRED_SECTIONS = {
        "summary": "Game summary",
        "narrative": "Narrative direction",
        "npcs": "NPC definitions",
        "quests": "Quest definitions",
        "levels": "Level or interaction data",
    }
    TRAILING_FRAGMENT_WORDS = {
        "a", "an", "and", "as", "at", "but", "for", "her", "his", "in",
        "its", "of", "or", "the", "their", "to", "with",
    }

    @staticmethod
    def _content(section: Dict[str, Any] | None) -> Dict[str, Any]:
        return section.get("content", {}) if isinstance(section, dict) else {}

    @staticmethod
    def _citations(section: Dict[str, Any] | None) -> List[Any]:
        citations = section.get("citations", []) if isinstance(section, dict) else []
        return citations if isinstance(citations, list) else []

    @staticmethod
    def _meaningful_text(value: Any, minimum_length: int = 12) -> bool:
        return isinstance(value, str) and len(value.strip()) >= minimum_length

    @classmethod
    def _looks_truncated(cls, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        text = value.strip()
        if not text:
            return False
        words = re.findall(r"[A-Za-z']+", text.lower())
        return bool(words and words[-1] in cls.TRAILING_FRAGMENT_WORDS and text[-1] not in ".!?\"'")

    @staticmethod
    def _looks_like_table_fragment(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        text = value.strip()
        return text.startswith("|") and text.count("|") >= 4

    def assess(self, blueprint: GameBlueprint) -> Dict[str, Any]:
        summary_section = blueprint.summary or {}
        narrative_section = blueprint.narrative_direction or {}
        npc_section = blueprint.npc_archetypes or {}
        quest_section = blueprint.quest_hooks or {}
        level_section = blueprint.level_design_suggestions or {}
        art_section = blueprint.art_style_direction or {}
        memory_section = blueprint.npc_memory_design or {}
        system_section = blueprint.gameplay_systems or {}

        summary = self._content(summary_section)
        narrative = self._content(narrative_section)
        npc_content = self._content(npc_section)
        quest_content = self._content(quest_section)
        level_content = self._content(level_section)
        art_content = self._content(art_section)
        memory_content = self._content(memory_section)
        system_content = self._content(system_section)

        npcs = npc_content.get("npcs") if isinstance(npc_content.get("npcs"), list) else []
        quests = quest_content.get("quests") if isinstance(quest_content.get("quests"), list) else []
        levels = level_content.get("levels") if isinstance(level_content.get("levels"), list) else []

        lore_background = narrative.get("lore_background")
        themes = narrative.get("themes") if isinstance(narrative.get("themes"), list) else []
        present = {
            "summary": self._meaningful_text(summary.get("title"), 2)
            and self._meaningful_text(summary.get("description")),
            "narrative": self._meaningful_text(lore_background) or bool(themes),
            "npcs": bool(npcs),
            "quests": bool(quests),
            "levels": bool(
                levels
                or self._meaningful_text(level_content.get("level_layout"))
                or level_content.get("interactive_elements")
            ),
        }
        missing_required = [
            label for key, label in self.REQUIRED_SECTIONS.items() if not present[key]
        ]
        blockers: List[str] = []
        advisories: List[str] = []

        if present["summary"] and self._looks_truncated(summary.get("description")):
            blockers.append("Game summary appears to end mid-sentence.")

        if present["narrative"]:
            if self._looks_like_table_fragment(lore_background):
                blockers.append("Narrative direction contains a raw table fragment instead of coherent story context.")
            elif self._looks_truncated(lore_background):
                blockers.append("Narrative direction appears to end mid-sentence.")

        for index, npc in enumerate(npcs, start=1):
            if not isinstance(npc, dict):
                blockers.append(f"NPC {index} is not a structured character record.")
                continue
            name = str(npc.get("name") or f"NPC {index}").strip()
            if not self._meaningful_text(npc.get("archetype"), 4):
                blockers.append(f"NPC '{name}' needs a usable role or archetype.")
            dialogue_style = npc.get("dialogue_style")
            if not self._meaningful_text(dialogue_style, 8):
                blockers.append(f"NPC '{name}' needs dialogue direction.")
            elif self._looks_truncated(dialogue_style):
                blockers.append(f"NPC '{name}' has a dialogue profile that ends mid-sentence.")

        for index, quest in enumerate(quests, start=1):
            if not isinstance(quest, dict):
                blockers.append(f"Quest {index} is not a structured quest record.")
                continue
            title = str(quest.get("title") or f"Quest {index}").strip()
            objective = quest.get("objective") or quest.get("description")
            if not self._meaningful_text(title, 3):
                blockers.append(f"Quest {index} needs a title.")
            if not self._meaningful_text(objective, 8):
                blockers.append(f"Quest '{title}' needs a concrete objective.")
            elif self._looks_truncated(objective):
                blockers.append(f"Quest '{title}' has an objective that ends mid-sentence.")

        for index, level in enumerate(levels, start=1):
            if not isinstance(level, dict):
                blockers.append(f"Level {index} is not a structured level record.")
                continue
            title = str(level.get("title") or f"Level {index}").strip()
            focus = level.get("focus") or level.get("description")
            if not self._meaningful_text(title, 2):
                blockers.append(f"Level {index} needs a title.")
            if not self._meaningful_text(focus, 8):
                blockers.append(f"Level '{title}' needs a playable focus or description.")
            elif self._looks_truncated(focus):
                blockers.append(f"Level '{title}' has a description that ends mid-sentence.")

        required_sections = {
            "Game summary": summary_section,
            "Narrative direction": narrative_section,
            "NPC definitions": npc_section,
            "Quest definitions": quest_section,
            "Level or interaction data": level_section,
        }
        for label, section in required_sections.items():
            if label not in missing_required and not self._citations(section):
                advisories.append(f"{label} has no source citation and needs manual evidence review.")

        if not (
            self._meaningful_text(art_content.get("visual_theme"), 3)
            or art_content.get("visual_notes")
            or art_content.get("color_palette")
        ):
            advisories.append("Art direction is not defined; visual production guidance is incomplete.")
        if not memory_content.get("memory_nodes"):
            advisories.append("NPC memory rules are not defined; runtime continuity will be limited.")
        if not (
            system_content.get("core_loop")
            or system_content.get("progression")
            or system_content.get("design_constraints")
        ):
            advisories.append("No explicit gameplay loop, progression, or design constraints were found.")

        # Preserve order while preventing repeated warnings from overwhelming the review UI.
        blockers = list(dict.fromkeys(blockers))
        advisories = list(dict.fromkeys(advisories))
        can_ship = not missing_required and not blockers

        if missing_required:
            status = "planning_only"
        elif blockers:
            status = "runtime_blocked"
        elif advisories:
            status = "runtime_review"
        else:
            status = "runtime_ready"

        return {
            "status": status,
            "can_approve": can_ship,
            "can_materialize": can_ship,
            "missing_required": missing_required,
            "blockers": blockers,
            "advisories": advisories,
        }
