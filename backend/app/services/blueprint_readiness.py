from typing import Any, Dict, List

from app.models.blueprint import GameBlueprint


class BlueprintReadinessService:
    """Assess whether source-grounded blueprint sections can form a useful runtime bundle."""

    REQUIRED_SECTIONS = {
        "npcs": "NPC definitions",
        "quests": "Quest definitions",
        "levels": "Level or interaction data",
    }

    @staticmethod
    def _content(section: Dict[str, Any] | None) -> Dict[str, Any]:
        return section.get("content", {}) if isinstance(section, dict) else {}

    def assess(self, blueprint: GameBlueprint) -> Dict[str, Any]:
        npc_content = self._content(blueprint.npc_archetypes)
        quest_content = self._content(blueprint.quest_hooks)
        level_content = self._content(blueprint.level_design_suggestions)
        system_content = self._content(blueprint.gameplay_systems)

        present = {
            "npcs": bool(npc_content.get("npcs")),
            "quests": bool(quest_content.get("quests")),
            "levels": bool(level_content.get("level_layout") or level_content.get("interactive_elements")),
            "gameplay_systems": bool(
                system_content.get("core_loop")
                or system_content.get("progression")
                or system_content.get("design_constraints")
            ),
        }
        missing_required = [label for key, label in self.REQUIRED_SECTIONS.items() if not present[key]]
        advisories: List[str] = []
        if not present["gameplay_systems"]:
            advisories.append("No explicit gameplay loop, progression, or design constraints were found.")

        if missing_required:
            status = "planning_only"
        elif advisories:
            status = "runtime_review"
        else:
            status = "runtime_ready"

        return {
            "status": status,
            "can_materialize": not missing_required,
            "missing_required": missing_required,
            "advisories": advisories,
        }
