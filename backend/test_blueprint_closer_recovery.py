"""Complete blueprint syntax may recover without inventing or rewriting data."""
import copy
import json

import pytest

from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, BlueprintContent
from app.design_agent.grounding import assess_artifact_quality
from app.design_agent.llm_provider import NvidiaStructuredOutputError
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from test_json_closer_recovery import invoke
from test_revision_completeness_guards import complete_artifact


def test_complete_critique_with_one_extra_outer_brace_preserves_every_finding():
    from app.design_agent.contracts import CritiqueOutput
    content = {"verdict": "needs_revision", "findings": [{
        "severity": "high", "section": "quest_hooks", "issue": 'Check {both} flags, not "either".',
        "recommendation": "Retain both recorded actions.",
    }], "summary": "Missing requested completion dialogue."}
    result, requests = invoke(json.dumps(content) + "\n}", model=CritiqueOutput)
    assert result.content == content and len(requests) == 1
    assert result.metadata["local_recovery"] and result.metadata["recovery_requires_review"]
    assert result.metadata["repair_attempts"] == 0
    assert result.metadata["validation_diagnostics"][0]["local_recovery"] == {
        "kind": "extra_critique_outer_brace", "removed_closers": 1,
    }


@pytest.mark.parametrize("kind", ["two_closers", "second_object", "prose", "missing_findings", "duplicate", "extra_field", "truncated"])
def test_critique_closer_recovery_cannot_discard_data_or_infer_fields(kind):
    from app.design_agent.contracts import CritiqueOutput
    content = {"verdict": "needs_revision", "findings": [], "summary": "Review required."}
    if kind == "missing_findings":
        content.pop("findings")
    if kind == "extra_field":
        content["unrecognized_review"] = "Do not discard this."
    raw = json.dumps(content) + "\n}"
    if kind == "two_closers":
        raw += "}"
    elif kind == "second_object":
        raw += '{"verdict":"ready_for_review"}'
    elif kind == "prose":
        raw = "Review output: " + raw
    elif kind == "duplicate":
        raw = raw.replace('"summary":', '"verdict":"ready_for_review", "summary":')
    from app.design_agent.llm_provider import NvidiaTruncatedOutputError
    with pytest.raises(NvidiaTruncatedOutputError if kind == "truncated" else NvidiaStructuredOutputError):
        invoke(raw, model=CritiqueOutput, finish_reason="length" if kind == "truncated" else "stop")


def test_recovered_critique_remains_blocked_and_preserves_original_findings():
    from app.design_agent.grounding import complete_design_critique, validate_design_approval
    from app.design_agent.llm_provider import CompletionResult
    content = complete_artifact()
    original = {"verdict": "ready_for_review", "findings": [{"severity": "medium", "section": "quest_hooks",
                "issue": "Original model finding.", "recommendation": "Review with source."}], "summary": "Review draft."}
    class RecoveredCritic:
        def complete(self, request):
            return CompletionResult(content=copy.deepcopy(original), provider_name="nvidia", model_name="fixture",
                                    metadata={"local_recovery": True, "recovery_requires_review": True})
    result = NvidiaDesignAgentProvider(llm_provider=RecoveredCritic()).critique(content, [])
    assert result.content["findings"][0] == original["findings"][0]
    assert result.content["verdict"] == "needs_revision"
    assert any(f["severity"] == "high" and "critique required closing-delimiter recovery" in f["issue"]
               for f in result.content["findings"])
    assert complete_design_critique(result.content, content) == result.content
    with pytest.raises(ValueError, match="Independent critique"):
        validate_design_approval(content, [], result.content)


@pytest.mark.parametrize("closers", [1, 2])
def test_complete_blueprint_recovers_only_outer_object_braces(closers):
    content = complete_artifact()
    # End with a section's warnings array so two absent object closers matches
    # the observed EOF diagnostic; no field, string or array data is missing.
    content = {key: {"content": content[key]["content"], "citations": content[key]["citations"],
                     "confidence": content[key]["confidence"], "warnings": []}
               for key in BLUEPRINT_SECTION_KEYS}
    raw = json.dumps(content, separators=(",", ":"))[:-closers]
    result, requests = invoke(raw, model=BlueprintContent)
    assert result.content == content
    assert len(requests) == 1
    assert result.metadata["local_recovery"] is True
    assert result.metadata["recovery_requires_review"] is True


def test_complete_blueprint_recovers_mistyped_content_object_closers_only():
    content = complete_artifact()
    # The saved CyberRakshak response made this same mistake in four sections.
    raw = json.dumps(content, separators=(",", ":"))
    assert raw.count('},"citations":') == len(BLUEPRINT_SECTION_KEYS)
    raw = raw.replace('},"citations":', '],"citations":', 4)
    result, requests = invoke(raw, model=BlueprintContent)
    assert result.content == content and len(requests) == 1
    assert result.metadata["local_recovery"] and result.metadata["recovery_requires_review"]
    recovery = result.metadata["validation_diagnostics"][0]["local_recovery"]
    assert recovery == {"kind": "mismatched_section_content_closers", "replaced_closers": 4}


@pytest.mark.parametrize("kind", ["missing_field", "duplicate_key", "unfinished", "inner_array", "prose"])
def test_mistyped_content_closer_does_not_relax_other_syntax_or_completeness_rules(kind):
    content = complete_artifact()
    if kind == "missing_field":
        content["summary"].pop("warnings")
    raw = json.dumps(content, separators=(",", ":")).replace('},"citations":', '],"citations":', 1)
    if kind == "duplicate_key":
        raw = raw[:-1] + ',"summary":' + json.dumps(content["summary"]) + '}'
    elif kind == "unfinished":
        raw = raw[:-1]
    elif kind == "inner_array":
        raw = raw.replace('"warnings":[]', '"warnings":[}', 1)
    elif kind == "prose":
        raw = "Here is the design: " + raw
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(raw, model=BlueprintContent)


@pytest.mark.parametrize("kind", ["missing_section", "missing_content", "missing_citations", "missing_warnings", "unknown_section", "unknown_section_field"])
def test_blueprint_recovery_cannot_infer_missing_fields_or_ignore_extra_fields(kind):
    content = complete_artifact()
    if kind == "missing_section":
        content.pop("summary")
    elif kind.startswith("missing_"):
        content["summary"].pop(kind.removeprefix("missing_"))
    elif kind == "unknown_section":
        content["extra"] = content["summary"]
    else:
        content["summary"]["extra"] = "not part of the section contract"
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(json.dumps(content)[:-1], model=BlueprintContent)


def test_blueprint_recovery_does_not_close_an_unfinished_array():
    content = complete_artifact()
    content["unity_runtime_preview"]["warnings"] = ["Review this proposal."]
    raw = json.dumps(content)[:-3]  # Missing array closer plus two object closers.
    with pytest.raises(NvidiaStructuredOutputError):
        invoke(raw, model=BlueprintContent)


def test_recovered_blueprint_is_visible_and_blocked_before_approval():
    from app.design_agent.llm_provider import CompletionResult

    content = complete_artifact()
    original = copy.deepcopy(content)

    class RecoveredTransport:
        def complete(self, request):
            return CompletionResult(content=copy.deepcopy(content), provider_name="nvidia", model_name="fixture",
                                    metadata={"local_recovery": True, "recovery_requires_review": True})

    result = NvidiaDesignAgentProvider(llm_provider=RecoveredTransport()).generate({"objective": "Build a design."}, [])
    assert content == original
    for section in BLUEPRINT_SECTION_KEYS:
        assert result.content[section]["content"] == original[section]["content"]
        assert any("local structural recovery" in warning for warning in result.content[section]["warnings"])
    scorecard = assess_artifact_quality(result.content)
    assert scorecard["passed"] is False
    assert "Recovered output" in scorecard["blockers"]


def test_recovery_cannot_be_hidden_by_complete_content_or_resolved_record_assumptions():
    content = complete_artifact()
    content["summary"]["warnings"] = [
        "The blueprint response required closing-delimiter recovery. Check the complete draft before approval."
    ]
    scorecard = assess_artifact_quality(content)
    assert "Recovered output" in scorecard["blockers"]
    assert next(item for item in scorecard["metrics"] if item["key"] == "integration_readiness")["value"] == 0.0
