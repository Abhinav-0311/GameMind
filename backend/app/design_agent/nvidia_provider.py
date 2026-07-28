import json
from dataclasses import replace
from typing import Any

from pydantic import BaseModel

from app.design_agent.contracts import BlueprintContent, CritiqueOutput, ResearchPlan
from app.design_agent.llm_provider import (
    CompletionRequest,
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
        result = self.llm_provider.complete(
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
        return ProviderResult(
            content=result.content,
            model_name=result.model_name,
            provider_name=result.provider_name,
            usage=result.usage,
            metadata=result.metadata,
        )

    def plan(self, objective: str, document_ids: list[str]) -> ProviderResult:
        return self._invoke(
            node_name="plan",
            expected_model=ResearchPlan,
            instruction=(
                "Create one concise retrieval plan for the selected game-design "
                "documents. Include every required GameMind blueprint section."
            ),
            payload={"objective": objective, "document_ids": document_ids},
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
                "chunk_id present in the supplied evidence. Put unsupported design "
                "decisions in warnings instead of presenting them as source facts."
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
                "only the supplied evidence and preserve unrelated valid sections."
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
        try:
            return getattr(self.primary, method_name)(*args)
        except NvidiaProviderError as error:
            fallback_result = getattr(self.fallback, method_name)(*args)
            return replace(
                fallback_result,
                metadata={
                    **fallback_result.metadata,
                    "degraded": True,
                    "fallback_from": self.primary.name,
                    "fallback_to": self.fallback.name,
                    "failure_code": error.code,
                    "primary_attempts": error.attempts,
                    "primary_retryable": error.retryable,
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
