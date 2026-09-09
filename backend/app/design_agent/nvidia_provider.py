import copy
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
    ResearchPlan,
    RetrievalPlanOutput,
    build_section_queries,
)
from app.design_agent.grounding import review_targets
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

    @staticmethod
    def _guided_json_enabled() -> bool:
        """Allow hosted NVIDIA endpoints without legacy guided_json support."""
        return os.getenv("NVIDIA_GUIDED_JSON_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

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
        use_guided_json = self._guided_json_enabled() and node_name in {
            "generate_blueprint",
            "critique",
            "revise",
        }
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
                "detail as an empty array. Quest dependencies must be explicitly supported by "
                "the supplied evidence; never invent prerequisite names. When no dependency is "
                "supported, return an empty dependencies array. The plan may contain "
                "resolved_decisions: treat those as binding human design direction for this "
                "run, but do not present them as GDD facts or cite them as source chunks. "
                "If a resolved decision conflicts with supplied evidence, preserve the conflict "
                "as an assumption requiring human confirmation. Set a quest's runtime binding "
                "only when the evidence explicitly supplies its quest giver, difficulty, rewards, "
                "and every objective target; otherwise leave runtime null. Keep the complete "
                "JSON compact: no more than three short items in any list, except a quest may "
                "have four ordered objectives. Do not repeat the same fact across fields. For a "
                "section with no section-matched evidence, return content as an empty object, "
                "an empty citations list, Low confidence, and one warning that human input is "
                "required; do not invent a proposal for that section."
            ),
            payload={"plan": plan, "evidence": compacted_evidence},
        )
        return broad

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
        result = self._invoke(
            node_name="revise",
            expected_model=BlueprintContent,
            instruction=(
                "Revise the blueprint to address the human rejection reason. Reuse "
                "only the supplied evidence and preserve unrelated source facts, but "
                "return a compact complete replacement rather than copying prose exactly. "
                "Materially update the targeted section's structured fields; a revision "
                "note without corrected design data is not a valid revision. Do not repeat "
                "facts across fields. Limit every list to three short items, except a quest "
                "may have four ordered objectives. For every section without section-matched "
                "evidence, return content as an empty object, an empty citations list, Low "
                "confidence, and one warning that human input is required."
            ),
            payload={
                "artifact": artifact,
                "evidence": compacted_evidence,
                "rejection_reason": rejection_reason,
            },
        )
        # The hosted model returns a complete BlueprintContent object, but a
        # human rejection authorizes changes only to its named sections. Keep
        # every other section byte-for-byte from the prior artifact so a
        # cosmetic model rewrite cannot bypass the human review boundary.
        targets = review_targets(rejection_reason)
        revised = copy.deepcopy(artifact)
        for section_name in targets:
            revised[section_name] = result.content[section_name]
        return replace(
            result,
            content=revised,
            metadata={
                **result.metadata,
                "revision_targets": targets,
                "preserved_unrelated_sections": [
                    section for section in BLUEPRINT_SECTION_KEYS if section not in targets
                ],
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
