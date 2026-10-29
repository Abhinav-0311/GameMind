"""Frozen QA controls: input integrity and trust gates, not hosted model accuracy."""
import copy
import hashlib
import json
from pathlib import Path

import jsonpatch
import pytest

from app.design_agent.contracts import GovernedBlueprintContent
from app.design_agent.finding_reviews import _artifact_value
from app.design_agent.grounding import _has_design_content, assess_artifact_quality, complete_design_critique, critic_reference_errors, validate_design_approval


FIXTURE = Path(__file__).parent / "tests/fixtures/critic_review_controls.json"
CONTROLS = json.loads(FIXTURE.read_text(encoding="utf-8"))


def control_input(case):
    base = CONTROLS["baselines"][case["baseline"]]
    artifact = jsonpatch.apply_patch(base["artifact"], case["patch"], in_place=False)
    return GovernedBlueprintContent.model_validate(artifact).model_dump(), copy.deepcopy(base["evidence"])


def test_frozen_controls_retain_exact_bundled_source_excerpts():
    root = Path(__file__).resolve().parent.parent
    for base in CONTROLS["baselines"].values():
        source = (root / base["source_path"]).read_text(encoding="utf-8")
        assert hashlib.sha256(source.encode()).hexdigest() == base["source_sha256"]
        assert all(item["content"] in source for item in base["evidence"])
    assert len({case["id"] for case in CONTROLS["cases"]}) == len(CONTROLS["cases"]) == 6


@pytest.mark.parametrize("case", CONTROLS["cases"], ids=lambda case: case["id"])
def test_control_inputs_are_valid_and_expectations_have_exact_references(case):
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider

    before = copy.deepcopy(CONTROLS)
    artifact, evidence = control_input(case)
    frozen_ids = {item["chunk_id"] for item in evidence}
    for section in artifact.values():
        assert set(section["citations"]) <= frozen_ids
    assert bool(case["expected_defects"]) == bool(case["patch"])
    for defect in case["expected_defects"]:
        assert defect["reason"] and defect["counterexample"]
        for path in defect["artifact_paths"]:
            _artifact_value(artifact, path)
        if defect["evidence_chunk_id"]:
            passage = next(item["content"] for item in evidence if item["chunk_id"] == defect["evidence_chunk_id"])
            assert defect["evidence_quote"] and defect["evidence_quote"] in passage
        else:
            assert defect["evidence_quote"] is None
    base = CONTROLS["baselines"][case["baseline"]]
    wire = {"review_mode": "defect_detection", "summary": "Controlled adapter check; not model accuracy.", "findings": [],
        "source_coverage": {section: "deferred" if section == "unity_runtime_preview" else
                            "covered" if _has_design_content(artifact[section]["content"]) else "not_specified"
                            for section in artifact}}
    capture = BlueprintCapturingProvider(wire)
    NvidiaDesignAgentProvider(llm_provider=capture).critique(artifact, evidence, review_request=base["review_request"])
    assert len(capture.requests) == 1
    prompt = capture.requests[0].messages[1]["content"]
    payload = json.loads(prompt.split("Input: ", 1)[1])
    assert "expected_defects" not in prompt and "must_not_flag" not in prompt
    assert len(evidence) <= 10 and all(len(item["content"]) <= 1200 for item in evidence)
    assert {item["chunk_id"]: item["content"] for item in payload["evidence"]} == {
        item["chunk_id"]: item["content"] for item in evidence}
    for defect in case["expected_defects"]:
        for path in defect["artifact_paths"]:
            assert _artifact_value(payload["artifact"], path) == _artifact_value(artifact, path)
    assert CONTROLS == before


def test_generated_note_cannot_serve_as_gdd_evidence_in_the_frozen_valid_control():
    case = next(case for case in CONTROLS["cases"] if case["id"] == "cyber-valid")
    artifact, evidence = control_input(case)
    path = "/npc_archetypes/content/npcs/0/implementation_notes/0"
    note = _artifact_value(artifact, path)
    finding = {"section": "npc_archetypes", "severity": "medium", "issue": "Controlled invalid source quote.",
        "recommendation": "Compare with actual frozen GDD evidence.", "reference": {
            "artifact_path": path, "artifact_value": note,
            "evidence_chunk_id": evidence[0]["chunk_id"], "evidence_quote": note}}
    review = {"review_mode": "defect_detection", "verdict": "ready_for_review",
              "summary": "Replayed source-boundary error, not a new model response.", "findings": [finding]}
    before = copy.deepcopy((artifact, evidence, review))
    assert len(critic_reference_errors(review, artifact, evidence)) == 1
    checked = complete_design_critique(review, artifact,
        review_request=CONTROLS["baselines"][case["baseline"]]["review_request"], evidence=evidence)
    assert checked["verdict"] == "needs_revision"
    assert any("Critic reference validation failed" in item["issue"] for item in checked["findings"])
    assert (artifact, evidence, review) == before


@pytest.mark.parametrize("case_id,expected", [("frost-valid", False), ("frost-progress-state", True)])
def test_local_progress_check_distinguishes_frozen_condition_from_state_claim(case_id, expected):
    case = next(case for case in CONTROLS["cases"] if case["id"] == case_id)
    artifact, evidence = control_input(case)
    before = copy.deepcopy((artifact, evidence))
    score = assess_artifact_quality(artifact, review_request=CONTROLS["baselines"][case["baseline"]]["review_request"], evidence=evidence)
    assert ("dialogue_progress_state" in {gap["code"] for gap in score["request_coverage_gaps"]}) is expected
    assert (artifact, evidence) == before


@pytest.mark.parametrize("case_id", ["frost-valid", "cyber-valid"])
def test_uncited_unknown_memory_needs_coverage_review_not_invented_content(case_id):
    case = next(case for case in CONTROLS["cases"] if case["id"] == case_id)
    artifact, evidence = control_input(case)
    request = CONTROLS["baselines"][case["baseline"]]["review_request"]
    before = copy.deepcopy((artifact, evidence))
    raw = {"review_mode": "defect_detection", "verdict": "ready_for_review", "summary": "No model findings.", "findings": []}
    reviewed = complete_design_critique(raw, artifact, review_request=request, evidence=evidence)
    memory = [finding for finding in reviewed["findings"] if finding["section"] == "npc_memory_design"]
    assert len(memory) == 1 and memory[0]["severity"] == "medium"
    assert "Source coverage" in memory[0]["issue"]
    assert "do not invent" in memory[0]["recommendation"]
    assert not reviewed["quality_scorecard"]["passed"]
    assert "npc_memory_design" in reviewed["quality_scorecard"]["incomplete_sections"]
    with pytest.raises(ValueError):
        validate_design_approval(artifact, evidence, raw, review_request=request)
    # A warning cannot hide an empty, cited section or weaken an existing model finding.
    artifact["npc_memory_design"]["citations"] = [evidence[0]["chunk_id"]]
    raw["findings"] = [{"section": "npc_memory_design", "severity": "high", "issue": "Independent concern", "recommendation": "Review it."}]
    cited = complete_design_critique(raw, artifact, review_request=request, evidence=evidence)
    assert cited["findings"][0] == raw["findings"][0]
    assert any(finding["section"] == "npc_memory_design" and finding["issue"].startswith("Design content is empty")
               and finding["severity"] == "high" for finding in cited["findings"])
    artifact["npc_memory_design"]["citations"] = []
    assert (artifact, evidence) == before
