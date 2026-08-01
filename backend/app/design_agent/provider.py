import copy
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.design_agent.contracts import (
    BLUEPRINT_SECTION_KEYS,
    BlueprintContent,
    CritiqueOutput,
    ResearchPlan,
    build_section_queries,
)
from app.design_agent.grounding import review_target
from app.services.blueprint_service import BlueprintService


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
    provider_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _EvidenceChunk:
    id: str
    content: str
    chunk_index: int


class DesignAgentProvider(Protocol):
    name: str

    def configuration(self) -> dict[str, Any]: ...

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

    def configuration(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "models": {
                node_name: self.model_name
                for node_name in ("plan", "generate", "critique", "revise")
            },
            "fallback_enabled": False,
        }

    @staticmethod
    def _usage(*values: Any) -> ProviderUsage:
        input_size = sum(len(str(value).split()) for value in values)
        return ProviderUsage(input_tokens=input_size, output_tokens=max(1, input_size // 3))

    def plan(self, objective: str, document_ids: list[str]) -> ProviderResult:
        retrieval_query = (
            f"{objective} game design narrative NPC levels gameplay quests runtime"
        )
        plan = ResearchPlan(
            objective=objective,
            retrieval_query=retrieval_query,
            section_queries=build_section_queries(objective, retrieval_query),
        )
        return ProviderResult(
            content=plan.model_dump(),
            model_name=self.model_name,
            usage=self._usage(objective, document_ids),
            provider_name=self.name,
        )

    def generate(
        self,
        plan: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        blueprint = self._extract_blueprint(evidence)
        return ProviderResult(
            content=blueprint.model_dump(),
            model_name=self.model_name,
            usage=self._usage(plan, evidence),
            provider_name=self.name,
        )

    @staticmethod
    def _extract_blueprint(evidence: list[dict[str, Any]]) -> BlueprintContent:
        chunks = [
            _EvidenceChunk(
                id=str(item["chunk_id"]),
                content=str(item.get("content") or ""),
                chunk_index=int(item.get("chunk_index") or 0),
            )
            for item in evidence
            if item.get("chunk_id") and item.get("content")
        ]
        document_title = next(
            (str(item["title"]) for item in evidence if item.get("title")),
            "GameMind design-agent blueprint",
        )
        game_project_id = next(
            (
                str(item["game_project_id"])
                for item in evidence
                if item.get("game_project_id")
            ),
            "local_project",
        )
        sections = BlueprintService().extract_sections_from_chunks(
            document_title,
            chunks,
            game_project_id,
        )
        runtime_citations = [
            str(item["chunk_id"])
            for item in evidence
            if "unity_runtime_preview" in (item.get("matched_sections") or [])
        ][:5]
        sections["unity_runtime_preview"]["citations"] = runtime_citations
        sections["unity_runtime_preview"]["content"]["generation_mode"] = "mock"
        return BlueprintContent.model_validate(sections)

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
            provider_name=self.name,
        )

    def revise(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
        rejection_reason: str,
    ) -> ProviderResult:
        revised = copy.deepcopy(artifact)
        target = review_target(rejection_reason)
        extracted = self._extract_blueprint(evidence).model_dump()
        revised[target] = extracted[target]
        if target == "level_design_suggestions":
            level_match = re.search(
                r"\bLevel\s+(\d+)\s*:\s*([^.;]+)",
                rejection_reason,
                re.IGNORECASE,
            )
            evidence_text = "\n".join(
                str(item.get("content") or "") for item in evidence
            )
            if level_match and level_match.group(2).strip().lower() in evidence_text.lower():
                number = int(level_match.group(1))
                title = level_match.group(2).strip()
                levels = revised[target]["content"].setdefault("levels", [])
                replacement = {
                    "number": number,
                    "title": title,
                    "focus": f"Human-directed correction: {rejection_reason}",
                }
                existing_index = next(
                    (
                        index
                        for index, level in enumerate(levels)
                        if int(level.get("number", -1)) == number
                    ),
                    None,
                )
                if existing_index is None:
                    levels.append(replacement)
                    levels.sort(key=lambda level: int(level.get("number", 0)))
                else:
                    levels[existing_index] = replacement
        revised[target]["content"]["review_adjustments"] = [rejection_reason]
        revised[target]["warnings"] = list(
            dict.fromkeys(revised[target].get("warnings", []))
        )
        BlueprintContent.model_validate(revised)
        return ProviderResult(
            content=revised,
            model_name=self.model_name,
            usage=self._usage(artifact, evidence, rejection_reason),
            provider_name=self.name,
        )
