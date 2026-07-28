import json
import time
from dataclasses import dataclass, replace
from typing import Any, Callable

import httpx
from pydantic import BaseModel, ValidationError

from app.design_agent.contracts import BlueprintContent, CritiqueOutput, ResearchPlan
from app.design_agent.provider import (
    DesignAgentProvider,
    ProviderResult,
    ProviderUsage,
)


class NvidiaProviderError(RuntimeError):
    """Safe provider error that never includes response bodies or credentials."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool = False,
        attempts: int = 1,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.attempts = attempts


class NvidiaConfigurationError(NvidiaProviderError):
    pass


class NvidiaAuthenticationError(NvidiaProviderError):
    pass


class NvidiaStructuredOutputError(NvidiaProviderError):
    pass


@dataclass(frozen=True)
class NvidiaNodeConfig:
    model_name: str
    temperature: float
    max_tokens: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


@dataclass(frozen=True)
class _Completion:
    content: str
    input_tokens: int
    output_tokens: int
    attempts: int


class NvidiaDesignAgentProvider:
    """OpenAI-compatible NVIDIA inference with bounded reliability controls."""

    name = "nvidia"
    _RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        node_configs: dict[str, NvidiaNodeConfig],
        timeout_seconds: float,
        max_retries: int,
        retry_backoff_seconds: float,
        repair_enabled: bool,
        json_mode_enabled: bool = False,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.node_configs = node_configs
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.retry_backoff_seconds = max(0, retry_backoff_seconds)
        self.repair_enabled = repair_enabled
        self.json_mode_enabled = json_mode_enabled
        self._sleep = sleep
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Accept": "application/json"},
        )

        required_nodes = {"plan", "generate", "critique", "revise"}
        missing_nodes = required_nodes.difference(node_configs)
        if missing_nodes:
            raise ValueError(
                f"Missing NVIDIA model configuration for: {', '.join(sorted(missing_nodes))}"
            )

    def configuration(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "repair_enabled": self.repair_enabled,
            "json_mode_enabled": self.json_mode_enabled,
            "models": {
                node_name: config.as_dict()
                for node_name, config in self.node_configs.items()
            },
            "fallback_enabled": False,
        }

    @staticmethod
    def _schema_instruction(model: type[BaseModel]) -> str:
        return json.dumps(model.model_json_schema(), separators=(",", ":"))

    @staticmethod
    def _usage_value(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _extract_json(content: str) -> Any:
        candidate = content.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start >= 0 and end > start:
                return json.loads(candidate[start : end + 1])
            raise

    def _request_completion(
        self,
        *,
        node_name: str,
        messages: list[dict[str, str]],
    ) -> _Completion:
        if not self.api_key:
            raise NvidiaConfigurationError(
                "NVIDIA inference is selected but NVIDIA_API_KEY is not configured.",
                code="api_key_missing",
                attempts=0,
            )

        config = self.node_configs[node_name]
        payload = {
            "model": config.model_name,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        if self.json_mode_enabled:
            payload["response_format"] = {"type": "json_object"}
        maximum_attempts = self.max_retries + 1

        for attempt in range(1, maximum_attempts + 1):
            try:
                response = self._client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except httpx.TransportError as error:
                if attempt < maximum_attempts:
                    self._backoff(attempt)
                    continue
                raise NvidiaProviderError(
                    "NVIDIA inference did not respond within the configured reliability budget.",
                    code="provider_timeout",
                    retryable=True,
                    attempts=attempt,
                ) from error

            if response.status_code in {401, 403}:
                raise NvidiaAuthenticationError(
                    "NVIDIA rejected the configured credentials.",
                    code="authentication_failed",
                    attempts=attempt,
                )
            if response.status_code in self._RETRYABLE_STATUS_CODES:
                if attempt < maximum_attempts:
                    self._backoff(attempt)
                    continue
                raise NvidiaProviderError(
                    "NVIDIA inference remained unavailable after bounded retries.",
                    code="provider_unavailable",
                    retryable=True,
                    attempts=attempt,
                )
            if response.status_code >= 400:
                raise NvidiaProviderError(
                    f"NVIDIA rejected the inference request with HTTP {response.status_code}.",
                    code="request_rejected",
                    attempts=attempt,
                )

            try:
                envelope = response.json()
                content = envelope["choices"][0]["message"]["content"]
                usage = envelope.get("usage") or {}
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("empty model content")
            except (ValueError, KeyError, IndexError, TypeError) as error:
                raise NvidiaProviderError(
                    "NVIDIA returned an invalid completion envelope.",
                    code="invalid_response_envelope",
                    attempts=attempt,
                ) from error

            return _Completion(
                content=content,
                input_tokens=self._usage_value(usage.get("prompt_tokens")),
                output_tokens=self._usage_value(usage.get("completion_tokens")),
                attempts=attempt,
            )

        raise AssertionError("NVIDIA retry loop exited without a result.")

    def _backoff(self, attempt: int) -> None:
        delay = min(self.retry_backoff_seconds * (2 ** (attempt - 1)), 2.0)
        if delay:
            self._sleep(delay)

    def _validate_content(
        self,
        content: str,
        expected_model: type[BaseModel],
    ) -> dict[str, Any]:
        parsed = self._extract_json(content)
        return expected_model.model_validate(parsed).model_dump()

    def _invoke(
        self,
        *,
        node_name: str,
        expected_model: type[BaseModel],
        instruction: str,
        payload: dict[str, Any],
    ) -> ProviderResult:
        started = time.perf_counter()
        schema = self._schema_instruction(expected_model)
        completion = self._request_completion(
            node_name=node_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are GameMind's governed game-design agent. "
                        "Use only supplied evidence for factual claims. Return JSON only. "
                        f"The output must satisfy this JSON Schema: {schema}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"{instruction}\n\nINPUT:\n{json.dumps(payload, default=str)}",
                },
            ],
        )
        input_tokens = completion.input_tokens
        output_tokens = completion.output_tokens
        request_attempts = completion.attempts
        repaired = False
        repair_attempts = 0

        try:
            validated = self._validate_content(completion.content, expected_model)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as initial_error:
            if not self.repair_enabled:
                raise NvidiaStructuredOutputError(
                    "NVIDIA returned structured output that failed validation.",
                    code="structured_output_invalid",
                    attempts=request_attempts,
                ) from initial_error

            repair_attempts = 1
            repair_completion = self._request_completion(
                node_name=node_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Repair the supplied model output into valid JSON. "
                            "Do not add unsupported facts. Return JSON only. "
                            f"The output must satisfy this JSON Schema: {schema}"
                        ),
                    },
                    {"role": "user", "content": completion.content},
                ],
            )
            request_attempts += repair_completion.attempts
            input_tokens += repair_completion.input_tokens
            output_tokens += repair_completion.output_tokens
            try:
                validated = self._validate_content(
                    repair_completion.content,
                    expected_model,
                )
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as repair_error:
                raise NvidiaStructuredOutputError(
                    "NVIDIA structured-output repair failed its validation budget.",
                    code="structured_output_invalid",
                    attempts=request_attempts,
                ) from repair_error
            repaired = True

        return ProviderResult(
            content=validated,
            model_name=self.node_configs[node_name].model_name,
            provider_name=self.name,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
                latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            ),
            metadata={
                "degraded": False,
                "request_attempts": request_attempts,
                "retry_count": max(0, request_attempts - 1 - repair_attempts),
                "repair_attempts": repair_attempts,
                "repaired": repaired,
                "cost_status": "unavailable",
            },
        )

    def plan(self, objective: str, document_ids: list[str]) -> ProviderResult:
        return self._invoke(
            node_name="plan",
            expected_model=ResearchPlan,
            instruction=(
                "Create a concise research plan and one retrieval query for the selected "
                "game-design documents."
            ),
            payload={"objective": objective, "document_ids": document_ids},
        )

    def generate(
        self,
        plan: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ProviderResult:
        return self._invoke(
            node_name="generate",
            expected_model=BlueprintContent,
            instruction=(
                "Generate all blueprint sections. Every citation must reference a chunk_id "
                "present in the supplied evidence. Mark unsupported design decisions as warnings."
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
                "Independently critique the blueprint for unsupported claims, missing source "
                "coverage, contradictions, and unusable game-design output."
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
                "Revise the blueprint to address the human rejection reason. Reuse only the "
                "supplied evidence and preserve unrelated valid sections."
            ),
            payload={
                "artifact": artifact,
                "evidence": evidence,
                "rejection_reason": rejection_reason,
            },
        )


class ResilientDesignAgentProvider:
    """Optional, observable fallback from hosted NVIDIA inference to local mock."""

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
