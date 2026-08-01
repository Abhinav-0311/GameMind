import json
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
from app.design_agent.provider import DesignAgentProvider, ProviderResult


class NvidiaDesignAgentProvider:
    """GameMind prompts and contracts layered over the NVIDIA transport."""

    name = "nvidia"

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
        }

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
                            f"JSON Schema: {self._schema_instruction(expected_model)}\n"
                            f"Input: {json.dumps(payload, default=str)}"
                        ),
                    },
                ],
                response_model=expected_model,
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
        return self._invoke(
            node_name="generate_blueprint",
            expected_model=BlueprintContent,
            instruction=(
                "Generate all blueprint sections. Every citation must reference a "
                "chunk_id present in the supplied evidence and list the current section "
                "in that evidence item's matched_sections. Populate structured arrays "
                "such as levels, NPCs, systems, and quests when the evidence defines "
                "them. Put unsupported design decisions in warnings instead of "
                "presenting them as source facts."
            ),
            payload={"plan": plan, "evidence": evidence},
        )

    def critique(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        return self._invoke(
            node_name="critique",
            expected_model=CritiqueOutput,
            instruction=(
                "Independently critique the blueprint for unsupported claims, missing "
                "source coverage, contradictions, and unusable game-design output."
            ),
            payload={"artifact": artifact, "evidence": evidence},
        )

    def revise(
        self,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
        rejection_reason: str,
    ) -> ProviderResult:
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
                "evidence": evidence,
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
