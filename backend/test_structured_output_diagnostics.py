"""Safe metadata must explain failures without persisting model text or secrets."""
import json
import traceback
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.design_agent.llm_provider import CompletionRequest, NODE_MODEL_CONFIG, NvidiaProvider, NvidiaProviderError, NvidiaStructuredOutputError
from app.design_agent.workflow import DesignAgentWorkflow
from test_design_agent_llm_provider import _completion


class TinyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def invoke(contents, *, repair=False):
    remaining = iter(contents)
    provider = NvidiaProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1,
        repair_enabled=repair,
        client=httpx.Client(transport=httpx.MockTransport(lambda request: _completion(next(remaining)))),
        key_reader=lambda name: "credential-never-log", sleep=lambda seconds: None,
    )
    return provider.complete(CompletionRequest(
        node_name="revise", messages=[{"role": "user", "content": "private source never log"}],
        response_model=TinyResponse,
    ))


@pytest.mark.parametrize("raw,should_retry", [
    ('{"text":"private output never log",}' + '}]' * 40, False),
    ('{"text":"private output never log', True),
    ('{"text":"' + '}]' * 40, True),
])
def test_truncation_retry_does_not_extend_a_malformed_delimiter_loop(raw, should_retry):
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        return _completion(raw, finish_reason="length") if len(calls) == 1 else _completion('{"text":"usable"}')
    provider = NvidiaProvider(base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(respond)), key_reader=lambda _: "credential-never-log")
    request = CompletionRequest(node_name="revise", messages=[], response_model=TinyResponse, guided_json=True)
    if should_retry:
        result = provider.complete(request)
        assert result.content == {"text": "usable"} and len(calls) == 2
        assert calls[1]["max_tokens"] == calls[0]["max_tokens"] * 2
        assert calls[1]["response_format"] == calls[0]["response_format"]
    else:
        with pytest.raises(NvidiaStructuredOutputError) as caught:
            provider.complete(request)
        assert len(calls) == 1 and caught.value.attempts == 1
        assert caught.value.diagnostics["truncation_retry_skipped"] == "delimiter_loop"
        assert caught.value.diagnostics["completions"][0]["failure_kind"] == "json_syntax"
        rendered = json.dumps(caught.value.diagnostics) + str(caught.value)
        assert "private output never log" not in rendered and "credential-never-log" not in rendered


def test_json_syntax_failure_has_safe_position_and_no_exception_input():
    raw = '{"text":"private output never log" "other":1}'
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke([raw])
    details = caught.value.diagnostics
    diagnostic = details["completions"][0]
    assert diagnostic["failure_kind"] == "json_syntax"
    assert diagnostic["json_error"]["reason"] == "Expecting ',' delimiter"
    assert diagnostic["json_error"]["column"] > 0
    assert diagnostic["content_characters"] == len(raw)
    assert diagnostic["finish_reason"] == "stop"
    rendered = json.dumps(details) + "".join(traceback.format_exception(caught.value))
    for forbidden in [raw, "private output never log", "credential-never-log", "private source never log"]:
        assert forbidden not in rendered


def test_schema_error_preserves_known_fields_but_redacts_unknown_field_names():
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke([json.dumps({"text": {"secret-value": "do-not-log"}, "private-key-name": 1})])
    diagnostic = caught.value.diagnostics["completions"][0]
    assert diagnostic["failure_kind"] == "schema"
    assert {item["code"] for item in diagnostic["schema_errors"]} == {"string_type", "extra_forbidden"}
    assert ["text"] in [item["path"] for item in diagnostic["schema_errors"]]
    assert ["<unknown_field>"] in [item["path"] for item in diagnostic["schema_errors"]]
    assert "private-key-name" not in json.dumps(diagnostic)
    assert "do-not-log" not in json.dumps(diagnostic)


def test_successful_repair_keeps_initial_failure_and_valid_repair_summary():
    result = invoke(['{"text":', '{"text":"usable"}'], repair=True)
    records = result.metadata["validation_diagnostics"]
    assert [item["stage"] for item in records] == ["initial", "repair"]
    assert [item["failure_kind"] for item in records] == ["json_syntax", None]
    assert result.content == {"text": "usable"}


def test_failed_repair_retains_both_error_kinds_without_response_text():
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke(['{"text":', '{"text":null}'], repair=True)
    assert [item["failure_kind"] for item in caught.value.diagnostics["completions"]] == ["json_syntax", "schema"]
    assert caught.value.attempts == 2
    execution = SimpleNamespace(details={}, model_name=None)
    DesignAgentWorkflow._fail_execution(SimpleNamespace(commit=lambda: None), SimpleNamespace(), execution, 0, caught.value)
    # Equal token counts are two responses, not duplicate telemetry.
    assert (execution.input_tokens, execution.output_tokens) == (20, 10)


def test_workflow_failure_trace_retains_safe_provider_diagnostics():
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke(['{"text":'])
    execution = SimpleNamespace(details={}, model_name=None)
    run = SimpleNamespace()
    db = SimpleNamespace(commit=lambda: None)
    DesignAgentWorkflow._fail_execution(db, run, execution, 0, caught.value)
    assert execution.details["failure_code"] == "structured_output_invalid"
    assert execution.details["provider_diagnostics"]["completions"][0]["failure_kind"] == "json_syntax"
    assert execution.input_tokens == 10 and execution.output_tokens == 5
    assert execution.details["cost_status"] == "unavailable"


def test_schema_error_list_is_bounded():
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke([json.dumps({"text": "okay", **{f"private-{i}": i for i in range(60)}})])
    diagnostic = caught.value.diagnostics["completions"][0]
    assert len(diagnostic["schema_errors"]) == 20
    assert diagnostic["schema_error_count"] == 60


@pytest.mark.parametrize("syntax", ["wrong_content_closers", "missing_outer_closer"])
def test_schema_error_after_syntax_recovery_is_visible_and_not_sent_to_format_repair(syntax):
    from app.design_agent.contracts import GovernedBlueprintContent
    from test_design_contract_v2 import governed_artifact

    content = GovernedBlueprintContent.model_validate(governed_artifact()).model_dump()
    eligibility = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["eligibility"]
    eligibility.update(stage="greeting", quest_id=None, lifecycle="private-invalid-lifecycle", progress="any")
    original = json.dumps(content, separators=(",", ":"))
    raw = (original.replace('},"citations":', '],"citations":', 3)
           if syntax == "wrong_content_closers" else original[:-1])
    calls = []
    def handler(request):
        calls.append(request)
        return _completion(raw)
    provider = NvidiaProvider(base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)), key_reader=lambda _: "credential-never-log")
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        provider.complete(CompletionRequest(node_name="generate_blueprint", messages=[], response_model=GovernedBlueprintContent))
    assert len(calls) == caught.value.attempts == 1
    details = caught.value.diagnostics
    assert details["repair_skipped"] == "schema_after_syntax_recovery"
    diagnostic = details["completions"][0]
    assert diagnostic["failure_kind"] == "schema" and diagnostic["syntax_recovery_rejected"] is True
    assert diagnostic["json_error"]["reason"] == "Expecting ',' delimiter"
    assert {error["code"] for error in diagnostic["schema_errors"]} == {"literal_error"}
    assert diagnostic["schema_errors"][0]["path"][-2:] == ["eligibility", "lifecycle"]
    assert "local_recovery" not in diagnostic
    rendered = json.dumps(details) + "".join(traceback.format_exception(caught.value))
    assert "private-invalid-lifecycle" not in rendered and "credential-never-log" not in rendered
    assert json.dumps(content, separators=(",", ":")) == original


def test_format_repair_receives_safe_specific_validation_feedback():
    calls = []
    raw = '{"text":"private output never log" "other":1}'
    def handler(request):
        calls.append(json.loads(request.content))
        return _completion(raw if len(calls) == 1 else '{"text":"usable"}')
    provider = NvidiaProvider(base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)), key_reader=lambda _: "credential-never-log")
    provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=TinyResponse))
    prompt = calls[1]["messages"][1]["content"]
    feedback = json.loads(prompt.split("Validation errors: ", 1)[1].split("\nSchema:", 1)[0])
    assert feedback["json_error"]["reason"] == "Expecting ',' delimiter"
    assert feedback["json_error"]["line"] == 1 and feedback["json_error"]["column"] > 1
    assert feedback["failure_kind"] == "json_syntax"
    assert "private output never log" not in json.dumps(feedback)


@pytest.mark.parametrize("reason", ["private-finish-value", {"private": "value"}])
def test_unknown_finish_reason_is_not_logged(reason):
    provider = NvidiaProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=False,
        client=httpx.Client(transport=httpx.MockTransport(
            lambda request: _completion('{"text":"usable"}', finish_reason=reason))),
        key_reader=lambda name: "credential-never-log",
    )
    result = provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=TinyResponse))
    assert result.metadata["finish_reason"] == "unknown"
    assert "private" not in json.dumps(result.metadata)


def test_truncation_failure_retains_safe_sizes_and_finish_status():
    from app.design_agent.llm_provider import NvidiaTruncatedOutputError
    provider = NvidiaProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=False,
        client=httpx.Client(transport=httpx.MockTransport(
            lambda request: _completion("private partial text", finish_reason="length"))),
        key_reader=lambda name: "credential-never-log",
    )
    with pytest.raises(NvidiaTruncatedOutputError) as caught:
        provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=TinyResponse))
    records = caught.value.diagnostics["completions"]
    assert len(records) == 2
    assert all(item["failure_kind"] == "truncation" for item in records)
    assert "private partial text" not in json.dumps(records)


def test_repair_transport_failure_keeps_original_validation_diagnostic(monkeypatch):
    monkeypatch.setitem(NODE_MODEL_CONFIG, "revise", replace(NODE_MODEL_CONFIG["revise"], max_retries=0))
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return _completion('{"text":')
        raise httpx.ReadTimeout("private transport detail")

    provider = NvidiaProvider(
        base_url="https://example.invalid/v1", timeout_seconds=1, repair_enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        key_reader=lambda name: "credential-never-log",
    )
    with pytest.raises(NvidiaProviderError) as caught:
        provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=TinyResponse))
    assert caught.value.attempts == 2
    assert caught.value.diagnostics["repair_failure_code"] == "provider_timeout"
    assert caught.value.diagnostics["completions"][0]["failure_kind"] == "json_syntax"


@pytest.mark.parametrize("scenario,expected", [
    ("repair_invalid", (30, 12)),
    ("both_truncated", (30, 12)),
    ("truncation_then_invalid", (30, 12)),
    ("truncation_then_timeout", (10, 5)),
    ("repair_timeout", (10, 5)),
    ("repair_truncation_then_timeout", (30, 12)),
    ("repair_truncation_then_invalid", (60, 19)),
    ("repair_both_truncated", (60, 19)),
    ("transport_only", (0, 0)),
])
def test_failed_trace_counts_reported_completions_once_including_partial_transport_failures(monkeypatch, scenario, expected):
    monkeypatch.setitem(NODE_MODEL_CONFIG, "revise", replace(NODE_MODEL_CONFIG["revise"], max_retries=0))
    calls = []
    def handler(request):
        calls.append(request)
        index = len(calls)
        if (scenario == "transport_only"
                or (scenario in {"truncation_then_timeout", "repair_timeout"} and index == 2)
                or (scenario == "repair_truncation_then_timeout" and index == 3)):
            raise httpx.ReadTimeout("private transport detail")
        length = (scenario == "both_truncated"
                  or (scenario.startswith("truncation_") and index == 1)
                  or (scenario.startswith("repair_truncation_") and index == 2)
                  or (scenario == "repair_both_truncated" and index >= 2))
        return _completion('{"text":', finish_reason="length" if length else "stop",
                           input_tokens=10 * index, output_tokens=5 if index == 1 else 7)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = NvidiaProvider(base_url="https://example.invalid/v1", timeout_seconds=1,
                                  repair_enabled=scenario.startswith("repair_"), client=client,
                                  key_reader=lambda _: "credential-never-log", sleep=lambda _: None)
        with pytest.raises(NvidiaProviderError) as caught:
            provider.complete(CompletionRequest(node_name="revise", messages=[], response_model=TinyResponse))
    execution = SimpleNamespace(details={}, model_name=None)
    DesignAgentWorkflow._fail_execution(SimpleNamespace(commit=lambda: None), SimpleNamespace(), execution, 0, caught.value)
    assert (execution.input_tokens, execution.output_tokens) == expected
    assert execution.details["request_attempts"] == len(calls)
    assert execution.details["token_usage_scope"] == ("completed_responses_only" if expected != (0, 0) else "unavailable")
    assert execution.details["cost_status"] == "unavailable"
    assert "private" not in json.dumps(execution.details) and "credential-never-log" not in json.dumps(execution.details)


def test_post_generation_validation_failure_retains_successful_provider_usage():
    from contextlib import nullcontext
    from uuid import uuid4
    from app.design_agent.provider import ProviderResult, ProviderUsage
    from app.models.design_agent import DesignAgentRun
    run = SimpleNamespace(id=uuid4())
    execution = SimpleNamespace(id=uuid4(), details={}, model_name=None)
    db = SimpleNamespace(commit=lambda: None, rollback=lambda: None,
                         get=lambda model, identity: run if model is DesignAgentRun else execution)
    workflow = object.__new__(DesignAgentWorkflow)
    workflow.provider = SimpleNamespace(name="nvidia")
    workflow._session = lambda: nullcontext(db)
    workflow._load_run = lambda db, state: run
    workflow._begin_execution = lambda *args, **kwargs: execution
    result = ProviderResult(content={}, model_name="fixture", provider_name="nvidia",
                            usage=ProviderUsage(input_tokens=21, output_tokens=8), metadata={"cost_status": "unavailable"})
    def persist(*args):
        raise ValueError("Draft failed grounding.")
    with pytest.raises(ValueError, match="grounding"):
        workflow._provider_node({}, "generate_blueprint", lambda: result, persist)
    assert (execution.input_tokens, execution.output_tokens) == (21, 8)
    assert execution.model_name == "fixture" and execution.status == "failed"
    assert execution.details["cost_status"] == "unavailable"
