import json
import os
import time
from dataclasses import replace
from typing import Any

from pydantic import BaseModel

from app.design_agent.contracts import (
    BLUEPRINT_SECTION_KEYS,
    BlueprintContent,
    CritiqueOutput,
    FocusedDeveloperPack,
    FocusedQuestPack,
    PatchDialoguePack,
    ResearchPlan,
    RetrievalPlanOutput,
    build_section_queries,
)
from app.design_agent.llm_provider import (
    CompletionRequest,
    CompletionResult,
    LLMProvider,
    NODE_MODEL_CONFIG,
    NvidiaAuthenticationError,
    NvidiaConfigurationError,
    NvidiaProviderError,
    NvidiaStructuredOutputError,
    NvidiaTruncatedOutputError,
)
from app.design_agent.provider import DesignAgentProvider, ProviderResult, ProviderUsage


class NvidiaDesignAgentProvider:
    """GameMind prompts and contracts layered over the NVIDIA transport."""

    name = "nvidia"
    _MAX_EVIDENCE_ITEMS = int(os.getenv("DESIGN_AGENT_EVIDENCE_MAX_ITEMS", "10"))
    _MAX_EVIDENCE_CHARS_PER_ITEM = int(
        os.getenv("DESIGN_AGENT_EVIDENCE_MAX_CHARS_PER_ITEM", "600")
    )

    def __init__(self, *, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    def configuration(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "models": {
                node_name: {
                    "provider": config.provider,
                    "model": config.model,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "max_retries": config.max_retries,
                }
                for node_name, config in NODE_MODEL_CONFIG.items()
            },
            "fallback_enabled": False,
            "evidence_payload": {
                "max_items": self._MAX_EVIDENCE_ITEMS,
                "max_chars_per_item": self._MAX_EVIDENCE_CHARS_PER_ITEM,
            },
        }

    @classmethod
    def _compact_evidence(cls, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Bound prompt size while retaining stable citation IDs and section provenance."""
        ranked = sorted(
            evidence,
            key=lambda item: (
                -len(item.get("matched_sections") or []),
                -float(item.get("similarity") or 0),
                item.get("chunk_index") or 0,
                str(item.get("chunk_id") or ""),
            ),
        )
        selected = ranked[: cls._MAX_EVIDENCE_ITEMS]
        compacted: list[dict[str, Any]] = []
        for item in selected:
            content = str(item.get("content") or "")
            excerpt = content[: cls._MAX_EVIDENCE_CHARS_PER_ITEM]
            compacted.append(
                {
                    **item,
                    "content": excerpt,
                    "content_truncated": len(content) > len(excerpt),
                }
            )
        return compacted

    @staticmethod
    def _schema_instruction(model: type[BaseModel]) -> str:
        return json.dumps(model.model_json_schema(), separators=(",", ":"))

    def _invoke(
        self,
        *,
        node_name: str,
        expected_model: type[BaseModel],
        instruction: str,
        payload: dict[str, Any],
    ) -> ProviderResult:
        result = self._complete(
            node_name=node_name,
            expected_model=expected_model,
            instruction=instruction,
            payload=payload,
        )
        return ProviderResult(
            content=result.content,
            model_name=result.model_name,
            provider_name=result.provider_name,
            usage=result.usage,
            metadata=result.metadata,
        )

    def _complete(
        self,
        *,
        node_name: str,
        expected_model: type[BaseModel],
        instruction: str,
        payload: dict[str, Any],
    ) -> CompletionResult:
        use_guided_json = node_name in {"generate_blueprint", "critique", "revise"}
        schema_instruction = (
            ""
            if use_guided_json
            else f"JSON Schema: {self._schema_instruction(expected_model)}\n"
        )
        return self.llm_provider.complete(
            CompletionRequest(
                node_name=node_name,
                messages=[
                    {"role": "system", "content": "detailed thinking off"},
                    {
                        "role": "user",
                        "content": (
                            "You are GameMind's governed game-design agent. "
                            "Use only supplied evidence for factual claims. "
                            "Return only valid JSON with no markdown or commentary.\n"
                            f"Task: {instruction}\n"
                            f"{schema_instruction}"
                            f"Input: {json.dumps(payload, default=str)}"
                        ),
                    },
                ],
                response_model=expected_model,
                guided_json=use_guided_json,
            )
        )

    def plan(self, objective: str, document_ids: list[str]) -> ProviderResult:
        result = self._complete(
            node_name="plan",
            expected_model=RetrievalPlanOutput,
            instruction=(
                "Create one concise semantic retrieval query that will find evidence "
                "for narrative, art direction, NPCs, memory, levels, gameplay systems, "
                "quests, and runtime integration. Return only retrieval_query."
            ),
            payload={"objective": objective, "document_ids": document_ids},
        )
        plan = ResearchPlan(
            objective=objective,
            retrieval_query=result.content["retrieval_query"],
            required_sections=list(BLUEPRINT_SECTION_KEYS),
            section_queries=build_section_queries(
                objective,
                result.content["retrieval_query"],
            ),
        )
        return ProviderResult(
            content=plan.model_dump(),
            model_name=result.model_name,
            provider_name=result.provider_name,
            usage=result.usage,
            metadata={
                **result.metadata,
                "deterministic_fields": ["objective", "required_sections"],
            },
        )

    def generate(
        self,
        plan: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        compacted_evidence = self._compact_evidence(evidence)
        broad = self._invoke(
            node_name="generate_blueprint",
            expected_model=BlueprintContent,
            instruction=(
                "Generate all blueprint sections. Every citation must reference a "
                "chunk_id present in the supplied evidence and list the current section "
                "in that evidence item's matched_sections. Populate structured arrays "
                "such as levels, NPCs, systems, and quests when the evidence defines "
                "them. For every NPC, include dialogue hooks, relationship notes, and "
                "implementation notes when supported. For every quest, include ordered "
                "objectives, failure states, dependencies, dialogue hooks, and implementation "
                "notes when supported. Put any useful but unsupported proposal in that "
                "record's assumptions list and state that it needs human confirmation; do not "
                "present it as a source fact. Every NPC and quest must include one or more "
                "source_chunk_ids from the supplied evidence. Generate at most two NPCs and two "
                "quests, prioritizing complete, distinctive records over coverage. Keep unavailable "
                "detail as an empty array."
            ),
            payload={"plan": plan, "evidence": compacted_evidence},
        )
        focused_evidence = [
            item for item in compacted_evidence
            if {"npc_archetypes", "quest_hooks"} & set(item.get("matched_sections") or [])
        ]
        focused = self._invoke(
            node_name="generate_blueprint",
            expected_model=FocusedDeveloperPack,
            instruction=(
                "Generate only two complete, developer-ready NPC profiles and two complete quests. "
                "Prioritize PATCH and Jay when supported. Every factual record needs source_chunk_ids. "
                "For each selected NPC include at least one distinctive dialogue hook drawn from or tightly "
                "paraphrased from its cited evidence; never invent personality traits. For each quest include "
                "at least one ordered objective; include a failure state and dependency when supported. Omit a "
                "record that cannot meet these requirements. Use assumptions for anything not supported."
            ),
            payload={"objective": plan.get("objective", ""), "evidence": focused_evidence},
        )
        content = dict(broad.content)
        content.update(focused.content)
        patch_evidence = [
            item for item in focused_evidence
            if "patch" in str(item.get("content") or "").lower()
        ]
        patch = self._invoke(
            node_name="generate_blueprint",
            expected_model=PatchDialoguePack,
            instruction=(
                "Return 1 to 3 PATCH companion dialogue lines only. Each line must be an exact "
                "quote or a close, concise paraphrase of the supplied PATCH evidence and cite its source_chunk_ids."
            ),
            payload={"evidence": patch_evidence},
        )
        npcs = content["npc_archetypes"]["content"]["npcs"]
        for npc in npcs:
            if npc["name"].strip().lower() == "patch":
                npc["dialogue_hooks"] = [line["text"] for line in patch.content["lines"]]
                npc["source_chunk_ids"] = list(dict.fromkeys(
                    npc["source_chunk_ids"] + [source for line in patch.content["lines"] for source in line["source_chunk_ids"]]
                ))
        quest = self._invoke(
            node_name="generate_blueprint",
            expected_model=FocusedQuestPack,
            instruction=(
                "Generate exactly one actionable Training Sandbox quest from the supplied quest and level evidence. "
                "Include cited source_chunk_ids, ordered objectives, a failure state, and a dependency. "
                "Do not invent numeric thresholds, reward amounts, or prerequisite level names. Put any such "
                "proposal in assumptions unless it appears explicitly in the supplied evidence."
            ),
            payload={"evidence": [item for item in focused_evidence if "quest_hooks" in (item.get("matched_sections") or [])]},
        )
        content["quest_hooks"]["content"]["quests"] = quest.content["quests"]
        return ProviderResult(
            content=content,
            model_name=focused.model_name,
            provider_name=focused.provider_name,
            usage=ProviderUsage(
                input_tokens=broad.usage.input_tokens + focused.usage.input_tokens + patch.usage.input_tokens + quest.usage.input_tokens,
                output_tokens=broad.usage.output_tokens + focused.usage.output_tokens + patch.usage.output_tokens + quest.usage.output_tokens,
                cost_usd=broad.usage.cost_usd + focused.usage.cost_usd + patch.usage.cost_usd + quest.usage.cost_usd,
                latency_ms=broad.usage.latency_ms + focused.usage.latency_ms + patch.usage.latency_ms + quest.usage.latency_ms,
            ),
            metadata={**focused.metadata, "focused_developer_pack": True},
        )

    def critique(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        compacted_evidence = self._compact_evidence(evidence)
        return self._invoke(
            node_name="critique",
            expected_model=CritiqueOutput,
            instruction=(
                "Independently critique the blueprint for unsupported claims, missing "
                "source coverage, contradictions, and unusable game-design output."
            ),
            payload={"artifact": artifact, "evidence": compacted_evidence},
        )

    def revise(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
        rejection_reason: str,
    ) -> ProviderResult:
        compacted_evidence = self._compact_evidence(evidence)
        return self._invoke(
            node_name="revise",
            expected_model=BlueprintContent,
            instruction=(
                "Revise the blueprint to address the human rejection reason. Reuse "
                "only the supplied evidence and preserve every unrelated section "
                "exactly. Materially update the targeted section's structured fields; "
                "a revision note without corrected design data is not a valid revision."
            ),
            payload={
                "artifact": artifact,
                "evidence": compacted_evidence,
                "rejection_reason": rejection_reason,
            },
        )


class ResilientDesignAgentProvider:
    """Observable fallback from hosted NVIDIA inference to deterministic mock."""

    def __init__(
        self,
        *,
        primary: DesignAgentProvider,
        fallback: DesignAgentProvider,
    ):
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name

    def configuration(self) -> dict[str, Any]:
        config = dict(self.primary.configuration())
        config["fallback_enabled"] = True
        config["fallback_provider"] = self.fallback.name
        return config

    def _call(self, method_name: str, *args: Any) -> ProviderResult:
        started = time.perf_counter()
        try:
            return getattr(self.primary, method_name)(*args)
        except NvidiaProviderError as error:
            fallback_result = getattr(self.fallback, method_name)(*args)
            total_latency_ms = max(
                fallback_result.usage.latency_ms,
                round((time.perf_counter() - started) * 1000),
            )
            primary_latency_ms = max(
                0,
                total_latency_ms - fallback_result.usage.latency_ms,
            )
            return replace(
                fallback_result,
                usage=replace(
                    fallback_result.usage,
                    latency_ms=total_latency_ms,
                ),
                metadata={
                    **fallback_result.metadata,
                    "degraded": True,
                    "fallback_from": self.primary.name,
                    "fallback_to": self.fallback.name,
                    "failure_code": error.code,
                    "primary_attempts": error.attempts,
                    "primary_retryable": error.retryable,
                    "primary_latency_ms": primary_latency_ms,
                    "cost_status": "unavailable",
                },
            )

    def plan(self, objective: str, document_ids: list[str]) -> ProviderResult:
        return self._call("plan", objective, document_ids)

    def generate(
        self,
        plan: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        return self._call("generate", plan, evidence)

    def critique(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        return self._call("critique", artifact, evidence)

    def revise(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
        rejection_reason: str,
    ) -> ProviderResult:
        return self._call("revise", artifact, evidence, rejection_reason)
