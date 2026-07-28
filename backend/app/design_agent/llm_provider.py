import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import httpx
from pydantic import BaseModel, ValidationError

from app.design_agent.provider import ProviderUsage


@dataclass(frozen=True)
class NodeModelConfig:
    provider: str
    model: str
    api_key_env: str
    temperature: float
    max_retries: int
    max_tokens: int


NODE_MODEL_CONFIG: dict[str, NodeModelConfig] = {
    "plan": NodeModelConfig(
        provider="nvidia",
        model="nvidia/llama-3.1-nemotron-nano-8b-v1",
        api_key_env="NVIDIA_NANO_API_KEY",
        temperature=0.0,
        max_retries=2,
        max_tokens=1200,
    ),
    "generate_blueprint": NodeModelConfig(
        provider="nvidia",
        model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
        api_key_env="NVIDIA_SUPER_API_KEY",
        temperature=0.0,
        max_retries=2,
        max_tokens=8000,
    ),
    "critique": NodeModelConfig(
        provider="nvidia",
        model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
        api_key_env="NVIDIA_SUPER_API_KEY",
        temperature=0.0,
        max_retries=2,
        max_tokens=4000,
    ),
    "revise": NodeModelConfig(
        provider="nvidia",
        model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
        api_key_env="NVIDIA_SUPER_API_KEY",
        temperature=0.0,
        max_retries=2,
        max_tokens=8000,
    ),
}


@dataclass(frozen=True)
class CompletionRequest:
    node_name: str
    messages: list[dict[str, str]]
    response_model: type[BaseModel]


@dataclass(frozen=True)
class CompletionResult:
    content: dict[str, Any]
    provider_name: str
    model_name: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str

    def complete(self, request: CompletionRequest) -> CompletionResult: ...


class NvidiaProviderError(RuntimeError):
    """Sanitized provider error that excludes response bodies and credentials."""

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


class NvidiaTruncatedOutputError(NvidiaProviderError):
    pass


@dataclass(frozen=True)
class _RawCompletion:
    content: str
    finish_reason: str | None
    input_tokens: int
    output_tokens: int
    request_attempts: int
    retry_count: int
    reasoning_discarded: bool


class MockProvider:
    """Deterministic per-node response queues for workflow and rejection tests."""

    name = "mock"

    def __init__(self, responses: dict[str, list[dict[str, Any] | str]]):
        self._responses = {
            node_name: list(node_responses)
            for node_name, node_responses in responses.items()
        }
        self._positions: dict[str, int] = defaultdict(int)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        responses = self._responses.get(request.node_name, [])
        position = self._positions[request.node_name]
        if position >= len(responses):
            raise RuntimeError(
                f"No scripted mock response remains for node '{request.node_name}'."
            )
        self._positions[request.node_name] += 1
        scripted = responses[position]
        parsed = json.loads(scripted) if isinstance(scripted, str) else scripted
        content = request.response_model.model_validate(parsed).model_dump()
        input_tokens = sum(
            len(message.get("content", "").split())
            for message in request.messages
        )
        return CompletionResult(
            content=content,
            provider_name=self.name,
            model_name="gamemind-scripted-mock-v1",
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=max(1, len(json.dumps(content).split())),
                cost_usd=0.0,
            ),
            metadata={
                "script_index": position,
                "request_attempts": 1,
                "retry_count": 0,
                "repair_attempts": 0,
                "truncation_retries": 0,
                "reasoning_discarded": False,
                "cost_status": "zero_cost_mock",
            },
        )


class NvidiaProvider:
    """Minimal NVIDIA transport implementing one governed completion operation."""

    name = "nvidia"
    _RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        repair_enabled: bool,
        client: httpx.Client | None = None,
        key_reader: Callable[[str], str | None] = os.getenv,
        sleep: Callable[[float], None] = time.sleep,
        retry_backoff_seconds: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.repair_enabled = repair_enabled
        self._key_reader = key_reader
        self._sleep = sleep
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Accept": "application/json"},
        )

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

    @staticmethod
    def _validate(
        content: str,
        response_model: type[BaseModel],
    ) -> dict[str, Any]:
        parsed = NvidiaProvider._extract_json(content)
        return response_model.model_validate(parsed).model_dump()

    def _backoff(self, attempt: int) -> None:
        delay = min(self.retry_backoff_seconds * (2 ** (attempt - 1)), 2.0)
        if delay:
            self._sleep(delay)

    def _send(
        self,
        *,
        config: NodeModelConfig,
        api_key: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> _RawCompletion:
        maximum_attempts = config.max_retries + 1
        for attempt in range(1, maximum_attempts + 1):
            try:
                response = self._client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.model,
                        "messages": messages,
                        "temperature": config.temperature,
                        "max_tokens": max_tokens,
                        "stream": False,
                    },
                    timeout=self.timeout_seconds,
                )
            except httpx.TransportError:
                if attempt < maximum_attempts:
                    self._backoff(attempt)
                    continue
                raise NvidiaProviderError(
                    "NVIDIA inference did not respond within the configured reliability budget.",
                    code="provider_timeout",
                    retryable=True,
                    attempts=attempt,
                ) from None

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
                choice = envelope["choices"][0]
                message = choice["message"]
                content = message.get("content") or ""
                usage = envelope.get("usage") or {}
                if not isinstance(content, str):
                    raise TypeError("completion content is not text")
            except (ValueError, KeyError, IndexError, TypeError) as error:
                raise NvidiaProviderError(
                    "NVIDIA returned an invalid completion envelope.",
                    code="invalid_response_envelope",
                    attempts=attempt,
                ) from error

            reasoning = (
                message.get("reasoning_content")
                or message.get("reasoning")
                or ""
            )
            return _RawCompletion(
                content=content,
                finish_reason=choice.get("finish_reason"),
                input_tokens=self._usage_value(usage.get("prompt_tokens")),
                output_tokens=self._usage_value(usage.get("completion_tokens")),
                request_attempts=attempt,
                retry_count=attempt - 1,
                reasoning_discarded=bool(reasoning),
            )

        raise AssertionError("NVIDIA retry loop exited without a result.")

    def _send_with_truncation_guard(
        self,
        *,
        config: NodeModelConfig,
        api_key: str,
        messages: list[dict[str, str]],
    ) -> tuple[_RawCompletion, int]:
        first = self._send(
            config=config,
            api_key=api_key,
            messages=messages,
            max_tokens=config.max_tokens,
        )
        if first.finish_reason != "length":
            return first, 0

        second = self._send(
            config=config,
            api_key=api_key,
            messages=messages,
            max_tokens=config.max_tokens * 2,
        )
        combined = _RawCompletion(
            content=second.content,
            finish_reason=second.finish_reason,
            input_tokens=first.input_tokens + second.input_tokens,
            output_tokens=first.output_tokens + second.output_tokens,
            request_attempts=first.request_attempts + second.request_attempts,
            retry_count=first.retry_count + second.retry_count,
            reasoning_discarded=(
                first.reasoning_discarded or second.reasoning_discarded
            ),
        )
        if second.finish_reason == "length":
            raise NvidiaTruncatedOutputError(
                "NVIDIA output remained truncated after one larger-budget retry.",
                code="output_truncated",
                retryable=False,
                attempts=combined.request_attempts,
            )
        return combined, 1

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if request.node_name not in NODE_MODEL_CONFIG:
            raise ValueError(
                f"No model configuration exists for node '{request.node_name}'."
            )
        config = NODE_MODEL_CONFIG[request.node_name]
        api_key = (self._key_reader(config.api_key_env) or "").strip()
        if not api_key:
            raise NvidiaConfigurationError(
                f"NVIDIA inference requires environment variable {config.api_key_env}.",
                code="api_key_missing",
                attempts=0,
            )

        started = time.perf_counter()
        completion, truncation_retries = self._send_with_truncation_guard(
            config=config,
            api_key=api_key,
            messages=request.messages,
        )
        input_tokens = completion.input_tokens
        output_tokens = completion.output_tokens
        request_attempts = completion.request_attempts
        retry_count = completion.retry_count
        reasoning_discarded = completion.reasoning_discarded
        repair_attempts = 0

        try:
            validated = self._validate(
                completion.content,
                request.response_model,
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as initial_error:
            if not self.repair_enabled:
                raise NvidiaStructuredOutputError(
                    "NVIDIA returned structured output that failed validation.",
                    code="structured_output_invalid",
                    attempts=request_attempts,
                ) from initial_error

            repair_attempts = 1
            schema = json.dumps(
                request.response_model.model_json_schema(),
                separators=(",", ":"),
            )
            repair, repair_truncation_retries = self._send_with_truncation_guard(
                config=config,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": "detailed thinking off"},
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY valid JSON matching this schema, no other text.\n"
                            f"Schema: {schema}\n"
                            f"Invalid output: {completion.content}"
                        ),
                    },
                ],
            )
            truncation_retries += repair_truncation_retries
            input_tokens += repair.input_tokens
            output_tokens += repair.output_tokens
            request_attempts += repair.request_attempts
            retry_count += repair.retry_count
            reasoning_discarded = (
                reasoning_discarded or repair.reasoning_discarded
            )
            try:
                validated = self._validate(
                    repair.content,
                    request.response_model,
                )
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as repair_error:
                raise NvidiaStructuredOutputError(
                    "NVIDIA structured-output repair failed its validation budget.",
                    code="structured_output_invalid",
                    attempts=request_attempts,
                ) from repair_error

        return CompletionResult(
            content=validated,
            provider_name=self.name,
            model_name=config.model,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
                latency_ms=max(
                    0,
                    round((time.perf_counter() - started) * 1000),
                ),
            ),
            metadata={
                "degraded": False,
                "request_attempts": request_attempts,
                "retry_count": retry_count,
                "repair_attempts": repair_attempts,
                "repaired": bool(repair_attempts),
                "truncation_retries": truncation_retries,
                "reasoning_discarded": reasoning_discarded,
                "finish_reason": "stop",
                "cost_status": "unavailable",
            },
        )
