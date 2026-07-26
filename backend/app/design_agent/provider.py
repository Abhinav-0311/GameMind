import copy
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.design_agent.contracts import (
    BLUEPRINT_SECTION_KEYS,
    BlueprintContent,
    CritiqueOutput,
    ResearchPlan,
)


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass(frozen=True)
class ProviderResult:
    content: dict[str, Any]
    model_name: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)


class DesignAgentProvider(Protocol):
    name: str

    def plan(self, objective: str, document_ids: list[str]) -> ProviderResult: ...

    def generate(
        self,
        plan: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult: ...

    def critique(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult: ...

    def revise(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
        rejection_reason: str,
    ) -> ProviderResult: ...


class MockDesignAgentProvider:
    """Deterministic provider used to prove orchestration without paid inference."""

    name = "mock"
    model_name = "gamemind-design-agent-mock-v1"

    @staticmethod
    def _usage(*values: Any) -> ProviderUsage:
        input_size = sum(len(str(value).split()) for value in values)
        return ProviderUsage(input_tokens=input_size, output_tokens=max(1, input_size // 3))

    def plan(self, objective: str, document_ids: list[str]) -> ProviderResult:
        plan = ResearchPlan(
            objective=objective,
            retrieval_query=f"{objective} game design narrative NPC levels gameplay quests runtime",
        )
        return ProviderResult(
            content=plan.model_dump(),
            model_name=self.model_name,
            usage=self._usage(objective, document_ids),
        )

    @staticmethod
    def _section(
        content: dict[str, Any],
        citations: list[str],
        warning: str | None = None,
    ) -> dict[str, Any]:
        return {
            "content": content,
            "citations": citations,
            "confidence": "Medium" if citations else "Low",
            "warnings": [warning] if warning else [],
        }

    def generate(
        self,
        plan: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        citations = [str(item["chunk_id"]) for item in evidence[:5] if item.get("chunk_id")]
        excerpts = [str(item.get("content", "")).strip() for item in evidence if item.get("content")]
        primary = excerpts[0][:900] if excerpts else None
        secondary = excerpts[1][:700] if len(excerpts) > 1 else primary
        missing = "No cited evidence was retrieved for this section."

        blueprint = BlueprintContent.model_validate(
            {
                "summary": self._section(
                    {"title": "GameMind design-agent blueprint", "description": primary},
                    citations[:2],
                    None if primary else missing,
                ),
                "narrative_direction": self._section(
                    {"lore_background": secondary, "themes": []},
                    citations[:3],
                    None if secondary else missing,
                ),
                "art_style_direction": self._section(
                    {"source_direction": primary, "palette": []},
                    citations[:2],
                    None if primary else missing,
                ),
                "npc_archetypes": self._section(
                    {"archetypes": [], "source_notes": secondary},
                    citations[:3],
                    "NPC roles require human confirmation.",
                ),
                "npc_memory_design": self._section(
                    {"memory_nodes": [], "continuity_source": secondary},
                    citations[:3],
                    "Memory rules require human confirmation.",
                ),
                "level_design_suggestions": self._section(
                    {"levels": [], "source_direction": primary},
                    citations[:3],
                    "Level coverage must be checked against the complete source.",
                ),
                "gameplay_systems": self._section(
                    {"systems": [], "source_direction": secondary},
                    citations[:3],
                    "Gameplay rules require human confirmation.",
                ),
                "quest_hooks": self._section(
                    {"quests": [], "source_direction": primary},
                    citations[:3],
                    "Quest hooks require human confirmation.",
                ),
                "unity_runtime_preview": self._section(
                    {
                        "npcs": [],
                        "levels": [],
                        "quests": [],
                        "version": "1.0.0",
                        "generation_mode": "mock",
                    },
                    citations,
                ),
            }
        )
        return ProviderResult(
            content=blueprint.model_dump(),
            model_name=self.model_name,
            usage=self._usage(plan, evidence),
        )

    def critique(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        findings = []
        for section_name in BLUEPRINT_SECTION_KEYS:
            section = artifact.get(section_name, {})
            for warning in section.get("warnings", []):
                findings.append(
                    {
                        "severity": "medium",
                        "section": section_name,
                        "issue": warning,
                        "recommendation": "Confirm this section against cited source evidence before approval.",
                    }
                )
            if not section.get("citations"):
                findings.append(
                    {
                        "severity": "high",
                        "section": section_name,
                        "issue": "The section has no supporting citation.",
                        "recommendation": "Add source evidence or explicitly mark the section as a design decision.",
                    }
                )

        critique = CritiqueOutput(
            verdict="needs_revision" if findings else "ready_for_review",
            findings=findings,
            summary=(
                f"Independent mock critique found {len(findings)} review item(s). "
                "Human approval remains authoritative."
            ),
        )
        return ProviderResult(
            content=critique.model_dump(),
            model_name=self.model_name,
            usage=self._usage(artifact, evidence),
        )

    def revise(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
        rejection_reason: str,
    ) -> ProviderResult:
        revised = copy.deepcopy(artifact)
        reason_lower = rejection_reason.lower()
        target = "summary"
        keyword_targets = (
            ("level", "level_design_suggestions"),
            ("npc", "npc_archetypes"),
            ("memory", "npc_memory_design"),
            ("quest", "quest_hooks"),
            ("gameplay", "gameplay_systems"),
            ("art", "art_style_direction"),
            ("narrative", "narrative_direction"),
            ("runtime", "unity_runtime_preview"),
        )
        for keyword, section_name in keyword_targets:
            if re.search(rf"\b{keyword}\w*\b", reason_lower):
                target = section_name
                break

        section = revised[target]
        section["content"]["human_revision"] = rejection_reason
        section["warnings"] = [
            warning
            for warning in section.get("warnings", [])
            if "human confirmation" not in warning.lower()
            and "coverage must be checked" not in warning.lower()
        ]
        BlueprintContent.model_validate(revised)
        return ProviderResult(
            content=revised,
            model_name=self.model_name,
            usage=self._usage(artifact, evidence, rejection_reason),
        )
