"""Offline regressions from the concrete Frostpeak QA failures; no hosted calls."""
import copy

import pytest
from pydantic import ValidationError

from app.design_agent.content_draft import ContentBlueprintDraft, assemble_content_draft, assemble_content_revision, project_content_revision
from app.design_agent.contracts import (
    BlueprintContent, GovernedBlueprintContent, GeneratedGovernedBlueprintContent,
    FreshGovernedBlueprintContent, critique_response_model, revision_response_model,
)
from app.design_agent.grounding import assess_artifact_quality, complete_design_critique, validate_generated_blueprint
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from app.design_agent.review_policy import canonical_review_request
from test_design_finding_resolutions import audit_client, post, submission
from test_nvidia_design_agent_provider import BlueprintCapturingProvider, content_draft_fixture
from test_quest_state_contract import typed_artifact


REQUEST = {"objective": "Review the draft", "design_contract_version": 2}


def governed_artifact():
    content = typed_artifact()
    content["narrative_direction"]["content"] = {"lore_background": "A guarded mountain pass.", "themes": ["Trust"]}
    content["art_style_direction"]["content"] = {"visual_theme": "Stylized fantasy", "visual_notes": ["Cold mountain paths"]}
    content["npc_memory_design"]["content"] = {"rules": ["Remember completed training objectives"]}
    content["level_design_suggestions"]["content"] = {"levels": [{"title": "Training pass", "focus": "Guards and the flagpole"}]}
    content["gameplay_systems"]["content"] = {"systems": [{"name": "Training", "description": "Clear guards and raise the flag"}]}
    quest = content["quest_hooks"]["content"]["quests"][0]
    contract = quest["state_contract"]
    contract["event_actions"] = {
        item["event"]: item["event"] for item in contract["objectives"]
    } | {contract["failure"]["events"][0]: "Player health reaches zero during the active attempt",
         contract["restart"]["event"]: "Player explicitly confirms starting a new attempt"}
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["dialogue_triggers"] = [{
        "trigger": "incomplete_progress",
        "situation": "Player has not completed both objectives",
        "text": "Your work at the pass is not yet finished.",
        "repeat_policy": "While eligible; no automatic restart",
        "eligibility": {"stage": "progress", "quest_id": quest["id"],
                        "lifecycle": "active", "progress": "incomplete"},
    }]
    npc.pop("dialogue_hooks", None)
    return content


def test_each_npc_dialogue_requirements_cannot_be_satisfied_by_another_npc():
    content = governed_artifact()
    first = content["npc_archetypes"]["content"]["npcs"][0]
    progress = copy.deepcopy(first["dialogue_triggers"][0])
    greeting = {**copy.deepcopy(progress), "trigger": "greet", "situation": "Greeting", "text": "Welcome.",
                "eligibility": {"stage": "greeting", "quest_id": None, "lifecycle": None, "progress": "any"}}
    completion = {**copy.deepcopy(progress), "trigger": "complete", "situation": "After quest completion",
                  "text": "Both tasks are complete.",
                  "eligibility": {**progress["eligibility"], "stage": "completion", "lifecycle": "completed", "progress": "complete"}}
    first["dialogue_triggers"] = [greeting, progress, completion]
    second = {**copy.deepcopy(first), "name": "Second NPC", "dialogue_triggers": [copy.deepcopy(greeting)]}
    content["npc_archetypes"]["content"]["npcs"].append(second)
    request = {**REQUEST, "objective": "For each source NPC, propose three spoken lines covering greeting, quest progress and completion."}
    def gaps():
        return [gap for gap in assess_artifact_quality(content, review_request=request)["request_coverage_gaps"]
                if gap["code"] in {"dialogue_greeting", "dialogue_progress", "dialogue_completion"}]
    assert [(gap["code"], gap["record"]) for gap in gaps()] == [
        ("dialogue_progress", "Second NPC"), ("dialogue_completion", "Second NPC")]
    # A workflow-wide request must not silently become a per-character requirement.
    request["objective"] = "Propose spoken dialogue covering greeting, quest progress and completion."
    assert not gaps()
    request["objective"] = "For every NPC, propose spoken lines covering greeting, quest progress and completion."
    second["dialogue_triggers"].extend([copy.deepcopy(progress), copy.deepcopy(completion)])
    assert not gaps()


def test_legacy_roundtrip_and_governed_requirements_are_separate():
    legacy = typed_artifact()
    assert BlueprintContent.model_validate(legacy).model_dump() == legacy
    with pytest.raises(ValidationError):
        GovernedBlueprintContent.model_validate(legacy)
    content = governed_artifact()
    assert GovernedBlueprintContent.model_validate(content).quest_hooks.content.quests[0].state_contract.event_actions
    with pytest.raises(ValidationError):
        validate_generated_blueprint(legacy, design_contract_version=2)


def test_governed_schema_requires_objectives_and_explicit_dialogue_mappings():
    schema = GovernedBlueprintContent.model_json_schema()["$defs"]
    assert "objectives" in schema["GovernedQuest"]["required"]
    assert schema["GovernedQuest"]["properties"]["objectives"]["minItems"] == 1
    assert "dialogue_triggers" in schema["GovernedNPC"]["required"]
    content = governed_artifact()
    content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"] = []
    assert GovernedBlueprintContent.model_validate(content)
    content["npc_archetypes"]["content"]["npcs"][0].pop("dialogue_triggers")
    assert BlueprintContent.model_validate(content)  # Historical profile-only drafts stay readable.


@pytest.mark.parametrize("model", [GeneratedGovernedBlueprintContent, FreshGovernedBlueprintContent])
def test_new_generation_derives_only_omitted_display_objectives(model):
    content = governed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    expected = quest.pop("objectives")
    before = copy.deepcopy(content)
    schema = model.model_json_schema()["$defs"]
    assert "objectives" not in schema["GeneratedGovernedQuest"]["properties"]
    assert schema["GeneratedGovernedQuestContent"]["properties"]["quests"]["maxItems"] == 2
    assert schema["FreshGovernedNPCContent"]["properties"]["npcs"]["maxItems"] == 2
    assert "objectives" in schema["GovernedQuestState"]["required"]
    result = model.model_validate(content).model_dump()
    assert result["quest_hooks"]["content"]["quests"][0]["objectives"] == expected
    assert content == before
    assert GovernedBlueprintContent.model_validate(result).model_dump() == result
    with pytest.raises(ValidationError):
        GovernedBlueprintContent.model_validate(content)  # Stored drafts are not upgraded.
    scoped = revision_response_model(["quest_hooks"], generated=True, design_contract_version=2,
                                     fresh_dialogue=model is FreshGovernedBlueprintContent)
    assert scoped.model_validate({"quest_hooks": content["quest_hooks"]}).model_dump() == {
        "quest_hooks": result["quest_hooks"]}


@pytest.mark.parametrize("fault", ["empty_display", "null_display", "conflict", "empty_state", "missing_state", "bad_flags"])
def test_generated_objective_derivation_does_not_repair_explicit_or_state_errors(fault):
    content = governed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    if fault == "empty_display":
        quest["objectives"] = []
    elif fault == "null_display":
        quest["objectives"] = None
    elif fault == "conflict":
        quest["objectives"][0] = "> " + quest["objectives"][0]
    else:
        quest.pop("objectives")
        if fault == "empty_state":
            quest["state_contract"]["objectives"] = []
        elif fault == "missing_state":
            quest.pop("state_contract")
        else:
            quest["state_contract"]["completion"]["required_flags"] = ["invented_flag"]
    before = copy.deepcopy(content)
    with pytest.raises(ValidationError):
        GeneratedGovernedBlueprintContent.model_validate(content)
    assert content == before


def test_guided_eligibility_branches_match_local_validation_exhaustively():
    import itertools
    import re
    from app.design_agent.contracts import DialogueEligibility

    schema = GovernedBlueprintContent.model_json_schema()["$defs"]["DialogueEligibility"]
    assert schema["required"] == ["stage", "quest_id", "lifecycle", "progress"]
    assert all(branch["required"] == schema["required"] for branch in schema["anyOf"])
    for stage, quest, lifecycle, progress in itertools.product(
        ("greeting", "progress", "completion", "other"),
        (None, "", "  ", "reclaim_ash_pass", " quest "),
        (None, "active", "failed", "completed"),
        ("incomplete", "complete", "any"),
    ):
        value = dict(stage=stage, quest_id=quest, lifecycle=lifecycle, progress=progress)
        try:
            DialogueEligibility.model_validate(value)
            valid = True
        except ValidationError:
            valid = False
        # Evaluate the emitted branch constraints; the base schema still owns types/enums.
        guided = any(
            stage in branch["properties"]["stage"]["enum"]
            and lifecycle == branch["properties"]["lifecycle"]["const"]
            and progress in branch["properties"]["progress"]["enum"]
            and (quest is None if branch["properties"]["quest_id"]["type"] == "null"
                 else isinstance(quest, str) and bool(re.search(
                     branch["properties"]["quest_id"]["pattern"], quest)))
            for branch in schema["anyOf"]
        )
        assert guided == valid, value


def test_saved_completion_mislabel_is_not_normalized_into_a_valid_mapping():
    content = governed_artifact()
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    mapping["eligibility"].update(stage="progress", lifecycle="completed", progress="complete")
    before = copy.deepcopy(content)
    with pytest.raises(ValidationError, match="Progress dialogue requires"):
        GovernedBlueprintContent.model_validate(content)
    assert content == before
    mapping["eligibility"]["stage"] = "completion"
    assert GovernedBlueprintContent.model_validate(content)


@pytest.mark.parametrize("missing", ["dialogue_triggers", "empty_dialogue"])
def test_new_governed_schema_rejects_missing_speech_without_changing_saved_profiles(missing):
    content = governed_artifact()
    if missing == "dialogue_triggers":
        content["npc_archetypes"]["content"]["npcs"][0].pop("dialogue_triggers")
    else:
        content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"] = []
    original = copy.deepcopy(content)
    assert BlueprintContent.model_validate(content)
    if missing == "empty_dialogue":
        assert GovernedBlueprintContent.model_validate(content)
    for model in (GeneratedGovernedBlueprintContent, FreshGovernedBlueprintContent):
        with pytest.raises(ValidationError):
            model.model_validate(content)
        scoped = revision_response_model(["npc_archetypes"], generated=True, design_contract_version=2,
                                         fresh_dialogue=model is FreshGovernedBlueprintContent)
        with pytest.raises(ValidationError):
            scoped.model_validate({"npc_archetypes": content["npc_archetypes"]})
    assert content == original


@pytest.mark.parametrize("fresh", [False, True])
def test_content_first_generation_and_existing_scoped_revision_require_speech(fresh, monkeypatch):
    import json
    import httpx
    from app.design_agent.contracts import FreshGovernedBlueprintContent
    from app.design_agent.llm_provider import NvidiaProvider
    from test_design_agent_llm_provider import _completion
    monkeypatch.setenv("NVIDIA_GUIDED_JSON_ENABLED", "true")
    content = governed_artifact()
    capture = BlueprintCapturingProvider(content)
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    request = {**REQUEST, "fresh_dialogue": fresh}
    provider.generate(request, [])
    assert capture.requests[-1].response_model is ContentBlueprintDraft
    provider.revise(content, [], "Make dialogue state-neutral", target_sections=["npc_archetypes", "quest_hooks"], review_request=request)
    schema = capture.requests[-1].response_model.model_json_schema()
    assert set(schema["properties"]) == {"changes"}
    assert set(schema["required"]) == {"changes"}
    assert "state_contract" not in str(schema) and "eligibility" not in str(schema)
    for completion_request in capture.requests:
        calls = []
        def respond(wire_request):
            payload = json.loads(wire_request.content)
            calls.append(payload)
            assert payload["response_format"]["json_schema"]["schema"] == completion_request.response_model.model_json_schema()
            wire = project_content_revision(content, ["npc_archetypes", "quest_hooks"])
            fixture = (content_draft_fixture(content) if completion_request.node_name == "generate_blueprint" else
                       {"changes": [{"artifact_path": "/quest_hooks/warnings", "replacement": wire["quest_hooks"]["warnings"]}]})
            returned = copy.deepcopy({key: fixture[key] for key in completion_request.response_model.model_fields})
            return _completion(json.dumps(returned))
        provider = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=False,
            key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond)))
        result = provider.complete(completion_request)
        from app.design_agent.content_draft import assemble_content_field_revision
        canonical = (assemble_content_draft(result.content) if completion_request.node_name == "generate_blueprint" else
                     assemble_content_field_revision(content, result.content, ["npc_archetypes", "quest_hooks"], []))
        assert canonical["quest_hooks"]["content"]["quests"][0]["objectives"] == content[
            "quest_hooks"]["content"]["quests"][0]["objectives"]
        assert len(calls) == 1


@pytest.mark.parametrize("model", [GeneratedGovernedBlueprintContent, FreshGovernedBlueprintContent])
def test_fresh_schema_retains_empty_unsupported_sections_and_closer_recovery(model):
    import json
    from app.design_agent.contracts import FreshGovernedBlueprintContent
    from test_json_closer_recovery import invoke
    content = governed_artifact()
    expected = content["quest_hooks"]["content"]["quests"][0].pop("objectives")
    result, calls = invoke(json.dumps(content)[:-1], model=model)
    assert len(calls) == 1 and result.metadata["local_recovery"]
    assert result.metadata["recovery_requires_review"] and not result.metadata["repair_attempts"]
    assert result.content["quest_hooks"]["content"]["quests"][0]["objectives"] == expected
    content["npc_archetypes"]["content"]["npcs"] = []
    content["quest_hooks"]["content"]["quests"] = []
    assert model.model_validate(content)  # No invented unsupported records.


def test_incomplete_governed_generation_does_not_spend_a_format_repair():
    import json
    import httpx
    from app.design_agent.llm_provider import CompletionRequest, NvidiaProvider, NvidiaStructuredOutputError
    from test_design_agent_llm_provider import _completion
    content = governed_artifact()
    content["quest_hooks"]["content"]["quests"][0].pop("objectives")
    calls = []
    def respond(request):
        calls.append(request)
        return _completion(json.dumps(content))
    provider = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=True,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond)))
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        provider.complete(CompletionRequest(node_name="generate_blueprint", messages=[], response_model=GovernedBlueprintContent))
    assert len(calls) == 1
    assert caught.value.diagnostics["repair_skipped"] == "governed_schema_failure"
    assert caught.value.diagnostics["completions"][0]["schema_errors"] == [
        {"code": "missing", "path": ["quest_hooks", "content", "quests", 0, "objectives"]}]


@pytest.mark.parametrize("change", [
    lambda c: c["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0].pop("eligibility"),
    lambda c: c["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["eligibility"].update(quest_id="unknown"),
    lambda c: c["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["eligibility"].update(lifecycle="failed"),
    lambda c: c["quest_hooks"]["content"]["quests"][0]["state_contract"]["event_actions"].pop("Player selects restart"),
    lambda c: c["quest_hooks"]["content"]["quests"][0]["state_contract"]["event_actions"].update(unused="Unrelated event action"),
    lambda c: c["quest_hooks"]["content"]["quests"][0]["state_contract"]["event_actions"].update({"Player selects restart": "player_confirms_restart"}),
])
def test_governed_output_rejects_missing_or_inconsistent_contract(change):
    content = governed_artifact()
    change(content)
    with pytest.raises(ValidationError):
        GovernedBlueprintContent.model_validate(content)


def test_structured_eligibility_catches_saved_partial_state_claim_without_prose_parser():
    content = governed_artifact()
    mapping = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    mapping["text"] = "The guards stand firm, and the flag lies low. Your resolve must yet be tested."
    score = assess_artifact_quality(content, review_request=REQUEST)
    assert "dialogue_progress_state" in {gap["code"] for gap in score["request_coverage_gaps"]}
    mapping["text"] = "Your work at the pass is not yet finished."
    assert not assess_artifact_quality(content, review_request=REQUEST)["request_coverage_gaps"]


@pytest.mark.parametrize("fault", ["missing", "stale", "noop", "wrong_section", "bad_quote"])
def test_critic_contract_keeps_raw_findings_but_blocks_invalid_anchors(fault):
    content = governed_artifact()
    path = "/npc_archetypes/content/npcs/0/dialogue_style"
    value = content["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"]
    finding = {"severity": "low", "section": "npc_archetypes", "issue": "Improve voice",
               "recommendation": "Make it shorter", "reference": {
                   "artifact_path": path, "artifact_value": value, "replacement": "Concise warnings",
                   "evidence_chunk_id": None, "evidence_quote": None}}
    if fault == "missing":
        finding.pop("reference")
    elif fault == "stale":
        finding["reference"]["artifact_value"] = "Not the current voice"
    elif fault == "noop":
        finding["reference"]["replacement"] = value
    elif fault == "wrong_section":
        finding["section"] = "quest_hooks"
    else:
        finding["reference"].update(evidence_chunk_id="source", evidence_quote="Not in evidence")
    raw = {"verdict": "ready_for_review", "findings": [finding], "summary": "Review complete"}
    before = copy.deepcopy(raw)
    reviewed = complete_design_critique(raw, content, review_request=REQUEST,
                                       evidence=[{"chunk_id": "source", "content": "Actual passage"}])
    assert raw == before and reviewed["findings"][0] == finding
    assert reviewed["verdict"] == "needs_revision"
    assert any(item["severity"] == "high" and "Critic reference" in item["issue"] for item in reviewed["findings"])


def test_adapter_and_scoped_revision_use_new_contract_only_when_versioned():
    content = governed_artifact()
    low_level = BlueprintCapturingProvider(content)
    provider = NvidiaDesignAgentProvider(llm_provider=low_level)
    assert provider.configuration()["design_contract_version"] == 2
    provider.generate(REQUEST, [])
    assert low_level.requests[-1].response_model is ContentBlueprintDraft
    targets = ["npc_archetypes", "quest_hooks"]
    request = {**REQUEST, "objective": "Propose failure and player-confirmed restart, not timers.",
               "fresh_dialogue": True}
    provider.revise(content, [], "Correct both records without changing source facts.", targets,
                    review_request=request)
    for captured in low_level.requests:
        prompt = captured.messages[1]["content"]
        if captured.node_name == "revise":
            assert set(captured.response_model.model_fields) == {"changes"}
            assert "Populate requested supported fields" in prompt
            assert "Preserve all unmentioned data" in prompt
            continue
        assert "Fill every supported section in the requested scope before expanding NPCs and quests" not in prompt
        assert "Preserve source-stated faction-choice consequences in narrative/systems" in prompt
        assert "Low retrieval similarity does not erase explicit facts" in prompt
        assert "A human request to propose failure/restart behavior permits concrete, labelled proposals" in prompt
        assert "Otherwise keep failure_states empty and restart_action null" in prompt
        assert "Compare each spoken claim against all eligible incomplete combinations" in prompt
        assert "Label each new speaker-to-quest association in that NPC's assumptions" in prompt
    assert set(low_level.requests[-1].response_model.model_fields) == {"changes"}
    strict = revision_response_model(["npc_archetypes"], generated=True, design_contract_version=2)
    missing = copy.deepcopy(content["npc_archetypes"])
    missing["content"]["npcs"][0]["dialogue_triggers"][0].pop("eligibility")
    with pytest.raises(ValidationError):
        strict.model_validate({"npc_archetypes": missing})
    assert canonical_review_request(REQUEST)["design_contract_version"] == 2
    assert "design_contract_version" not in canonical_review_request({"design_contract_version": True})


@pytest.mark.parametrize("valid_reference", [False, True])
@pytest.mark.parametrize("detection_only", [False, True])
def test_only_valid_critic_contracts_can_enter_human_resolution_approval(audit_client, valid_reference, detection_only):
    from app.design_agent.review_policy import build_review_provenance, validate_persisted_design_approval
    from test_finding_approval_policy import prepared

    client, db, url, run, artifact, snapshot, critique, proposals = prepared(audit_client)
    run.model_config = {**run.model_config, "design_contract_version": 2}
    content = governed_artifact()
    for section in content.values():
        section["citations"] = ["frozen-1"]
    for key, records in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
        for record in content[key]["content"][records]:
            record["source_chunk_ids"] = ["frozen-1"]
    content["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"] = "formal, slow"
    artifact.content = validate_generated_blueprint(content, snapshot.items, design_contract_version=2)
    voice = artifact.content["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"]
    raw = {"verdict": "needs_revision", "summary": "Voice concern",
           "source_coverage": {section: "covered" for section in governed_artifact()}, "findings": [{
        "severity": "high", "section": "npc_archetypes", "issue": "Incorrect voice",
        "recommendation": "Use the existing voice", "reference": {
            "artifact_path": "/npc_archetypes/content/npcs/0/dialogue_style", "artifact_value": voice,
            "replacement": "formal and slow" if valid_reference else voice, "evidence_chunk_id": "frozen-1",
            "evidence_quote": "Mira speaks in a formal and slow manner."}}]}
    if detection_only:
        raw["review_mode"] = "defect_detection"
        reference = raw["findings"][0]["reference"]
        reference.pop("replacement")
        if not valid_reference:
            reference["artifact_value"] = "Stale voice"
    critique.content = {**complete_design_critique(raw, artifact.content, review_request=REQUEST, evidence=snapshot.items),
        "model_review_provenance": build_review_provenance(raw, artifact.content, snapshot.items, REQUEST, clean=True)}
    # Use the same original objective for a valid provenance fingerprint.
    run.objective = REQUEST["objective"]
    db.commit()
    original = copy.deepcopy(critique.content)
    catalog = client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()
    assert catalog["critique_blocked"] and catalog["findings"][0]["can_resolve"] is valid_reference
    recorded = post(client, url, submission(client, url))
    assert recorded.status_code == (422 if detection_only and not valid_reference else 201)
    if recorded.status_code == 422:
        assert client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()["resolutions"] == []
    if valid_reference:
        proposals = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in assess_artifact_quality(artifact.content)["unresolved_assumptions"]]
        assert validate_persisted_design_approval(db, run, artifact, proposals)["passed"]
    else:
        with pytest.raises(ValueError, match="Independent critique"):
            validate_persisted_design_approval(db, run, artifact, proposals)
    assert critique.content == original and not artifact.immutable and artifact.blueprint_id is None


def test_governed_critic_repair_cannot_invent_missing_references():
    import json
    import httpx
    from app.design_agent.contracts import GovernedCritiqueOutput
    from app.design_agent.llm_provider import CompletionRequest, NvidiaProvider, NvidiaStructuredOutputError
    from test_design_agent_llm_provider import _completion

    raw = {"verdict": "needs_revision", "summary": "Voice concern",
           "source_coverage": {section: "covered" for section in governed_artifact()}, "findings": [{
        "severity": "high", "section": "npc_archetypes", "issue": "Voice", "recommendation": "Fix it"}]}
    calls = []
    def respond(request):
        calls.append(request)
        return _completion(json.dumps(raw))
    provider = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=True,
        key_reader=lambda _: "fake-test-key", sleep=lambda _: None,
        client=httpx.Client(transport=httpx.MockTransport(respond)))
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        provider.complete(CompletionRequest(node_name="critique", messages=[], response_model=GovernedCritiqueOutput))
    assert len(calls) == 1
    errors = caught.value.diagnostics["completions"][0]["schema_errors"]
    assert [error["path"] for error in errors] == [["findings", 0, "reference"]]


def test_workflow_does_not_let_planner_downgrade_saved_contract():
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from uuid import uuid4
    from app.design_agent.workflow import DesignAgentWorkflow
    from app.design_agent.provider import ProviderResult

    workflow = object.__new__(DesignAgentWorkflow)
    run = SimpleNamespace(id=uuid4(), game_project_id="test", objective="Review draft", document_ids=[],
        max_revisions=1, revision_count=0, model_config={"design_contract_version": 2})
    workflow._checkpointer = lambda: nullcontext(None)
    graph = MagicMock()
    graph.invoke.side_effect = lambda state, _: state
    workflow._compile = lambda _: graph
    state = workflow.start(run)
    assert state["design_contract_version"] == 2
    state.update(plan={"design_contract_version": 1}, evidence_items=[], evidence_snapshot_id=str(uuid4()))
    workflow.provider = MagicMock()
    workflow.provider.generate.return_value = ProviderResult(content=typed_artifact(), model_name="offline-test")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    workflow._provider_node = lambda state, name, call, persist: persist(db, run, call())
    with pytest.raises(ValidationError):
        workflow._generate_blueprint(state)
    assert workflow.provider.generate.call_args.args[0]["design_contract_version"] == 2
    db.add.assert_not_called()


def test_critic_targets_are_existing_canonical_paths_in_the_declared_section():
    content = governed_artifact()
    content["summary"]["content"]["a/b~c"] = "Exact escaped key"
    model = critique_response_model(content)
    schema = model.model_json_schema()
    assert "source_coverage" in schema["required"]
    assert set(schema["$defs"]["ArtifactCritiqueSourceCoverage"]["required"]) == set(content)
    finding = {"section": "npc_archetypes", "severity": "medium", "issue": "Voice concern",
               "recommendation": "Use a concise warning", "reference": {
                   "artifact_path": "/npc_archetypes/content/npcs/0/dialogue_style",
                   "artifact_value": "Brief warnings",
                   "evidence_chunk_id": None, "evidence_quote": None}}
    raw = {"review_mode": "defect_detection", "verdict": "needs_revision", "summary": "Review", "findings": [finding],
           "source_coverage": {section: "covered" for section in content}}
    assert model.model_validate(raw).model_dump() == raw
    for path, section in [
        ("/npc_archetypes/content/npcs[0]/dialogue_style", "npc_archetypes"),
        ("/npc_archetypes/content/npcs/10/dialogue_style", "npc_archetypes"),
        ("/quest_hooks/content/quests/0/failure_states", "npc_archetypes"),
        ("/quest_hooks/content/quests/0", "quest_hooks"),
        ("/npc_archetypes/content/npcs/0", "npc_archetypes"),
        ("/summary/content", "summary"),
    ]:
        finding["section"] = section
        finding["reference"]["artifact_path"] = path
        with pytest.raises(ValidationError):
            model.model_validate(raw)
    finding["section"] = "summary"
    finding["reference"].update(artifact_path="/summary/content/a~1b~0c", artifact_value="Exact escaped key")
    assert model.model_validate(raw).findings[0].reference.artifact_path.endswith("a~1b~0c")
    for value in (None, {}, {"existing_key": "Existing value"}, [], [{"title": "Existing level"}]):
        content["summary"]["content"]["a/b~c"] = value
        finding["reference"].update(artifact_value=value)
        assert critique_response_model(content).model_validate(raw).findings[0].reference.artifact_value == value
    content["summary"]["content"] = {}
    finding["reference"].update(artifact_path="/summary/content", artifact_value={})
    assert critique_response_model(content).model_validate(raw).findings[0].reference.artifact_value == {}


@pytest.mark.parametrize("fault", ["absent", "partial", "unanchored_missing", "ready_missing", "deferred_design"])
def test_governed_critic_requires_consistent_source_coverage(fault):
    content = governed_artifact()
    raw = {"review_mode": "defect_detection", "verdict": "needs_revision", "summary": "Missing source-backed summary.",
           "source_coverage": {section: "covered" for section in content}, "findings": [{
               "severity": "high", "section": "summary", "issue": "Source premise omitted.",
               "recommendation": "Include the stated premise.", "reference": {
                   "artifact_path": "/summary/content/description", "artifact_value": content["summary"]["content"]["description"],
                   "evidence_chunk_id": "frozen-1", "evidence_quote": "A mountain conflict."}}]}
    raw["source_coverage"]["summary"] = "missing"
    model = critique_response_model(content)
    assert model.model_validate(raw).model_dump() == raw
    if fault == "absent":
        raw.pop("source_coverage")
    elif fault == "partial":
        raw["source_coverage"].pop("npc_memory_design")
    elif fault == "unanchored_missing":
        raw["findings"][0]["reference"].update(evidence_chunk_id=None, evidence_quote=None)
    elif fault == "ready_missing":
        raw["verdict"] = "ready_for_review"
    else:
        raw["source_coverage"]["summary"] = "deferred"
    with pytest.raises(ValidationError):
        model.model_validate(raw)


def test_defect_detection_is_explicit_and_does_not_upgrade_legacy_noop_reviews():
    from app.design_agent.contracts import CritiqueOutput
    from app.design_agent.grounding import critic_reference_errors

    content = governed_artifact()
    raw = {"review_mode": "defect_detection", "verdict": "needs_revision", "summary": "Verify the voice.",
           "source_coverage": {section: "covered" for section in content}, "findings": [{
               "severity": "high", "section": "npc_archetypes", "issue": "Voice differs from the cited description.",
               "recommendation": "Compare the current voice with the frozen description before revision.",
               "reference": {"artifact_path": "/npc_archetypes/content/npcs/0/dialogue_style",
                   "artifact_value": content["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"],
                   "evidence_chunk_id": "source", "evidence_quote": "Voice: formal and slow."}}]}
    evidence = [{"chunk_id": "source", "content": "Voice: formal and slow."}]
    original = copy.deepcopy(raw)
    model = critique_response_model(content)
    assert "replacement" not in model.model_json_schema()["$defs"]["ArtifactCritiqueReference"]["properties"]
    assert model.model_validate(raw).model_dump() == raw
    assert CritiqueOutput.model_validate(raw).model_dump() == raw
    assert critic_reference_errors(raw, content, evidence) == []
    merged = complete_design_critique(raw, content, review_request=REQUEST, evidence=evidence)
    assert merged["verdict"] == "needs_revision" and merged["review_mode"] == "defect_detection"
    assert not any("Critic reference validation failed" in finding["issue"] for finding in merged["findings"])
    unmarked = copy.deepcopy(raw)
    unmarked.pop("review_mode")
    with pytest.raises(ValidationError):
        model.model_validate(unmarked)
    assert critic_reference_errors(unmarked, content, evidence)
    legacy = copy.deepcopy(unmarked)
    legacy["findings"][0]["reference"]["replacement"] = legacy["findings"][0]["reference"]["artifact_value"]
    assert "no-op" in critic_reference_errors(legacy, content, evidence)[0]
    forged = {**legacy, "review_mode": "defect_detection"}
    with pytest.raises(ValidationError):
        model.model_validate(forged)
    assert critic_reference_errors(forged, content, evidence)
    assert raw == original


@pytest.mark.parametrize("defer_runtime", [False, True])
def test_fresh_critic_runtime_coverage_is_bound_to_human_scope_without_hiding_defects(defer_runtime):
    content = governed_artifact()
    content["unity_runtime_preview"]["content"] = {"integration_notes": ["Unverified engine binding"]}
    original = copy.deepcopy(content)
    request = {**REQUEST, "defer_runtime": defer_runtime}
    raw = {"review_mode": "defect_detection", "verdict": "needs_revision", "summary": "Inspect runtime content.",
           "source_coverage": {section: "covered" for section in content}, "findings": [{
               "severity": "high", "section": "unity_runtime_preview", "issue": "Unverified runtime content remains.",
               "recommendation": "Review the runtime content against the run scope.", "reference": {
                   "artifact_path": "/unity_runtime_preview/content/integration_notes",
                   "artifact_value": ["Unverified engine binding"],
                   "evidence_chunk_id": None, "evidence_quote": None}}]}
    raw["source_coverage"]["unity_runtime_preview"] = "deferred" if defer_runtime else "covered"
    model = critique_response_model(content, defer_runtime=defer_runtime)
    assert model.model_validate(raw).model_dump() == raw
    coverage = model.model_json_schema()["$defs"]["ArtifactCritiqueSourceCoverage"]["properties"]["unity_runtime_preview"]
    if defer_runtime:
        assert coverage["const"] == "deferred"
    else:
        assert "deferred" not in coverage["enum"]
    wrong_scope = copy.deepcopy(raw)
    wrong_scope["source_coverage"]["unity_runtime_preview"] = "covered" if defer_runtime else "deferred"
    with pytest.raises(ValidationError):
        model.model_validate(wrong_scope)
    capture = BlueprintCapturingProvider(raw)
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [], review_request=request)
    assert result.metadata["finding_review_provenance"]["model_output"] == raw
    assert result.content["findings"][0] == raw["findings"][0]
    assert result.content["verdict"] == "needs_revision"
    if defer_runtime:
        assert "runtime_deferral_scope" in {gap["code"] for gap in result.content["quality_scorecard"]["request_coverage_gaps"]}
    assert content == original


def test_source_coverage_survives_review_provenance_without_changing_legacy_shape():
    from app.design_agent.contracts import CritiqueOutput
    from app.design_agent.review_policy import build_review_provenance, _trusted_model_review
    from types import SimpleNamespace

    content = governed_artifact()
    legacy = {"verdict": "ready_for_review", "summary": "Review.", "findings": []}
    assert CritiqueOutput.model_validate(legacy).model_dump() == legacy
    raw = {**legacy, "review_mode": "defect_detection", "source_coverage": {section: "covered" for section in content}}
    raw["source_coverage"].update(npc_memory_design="not_specified", unity_runtime_preview="deferred")
    assert critique_response_model(content, defer_runtime=True).model_validate(raw).model_dump() == raw
    corrective = {key: value for key, value in raw.items() if key != "review_mode"}
    for review in (legacy, corrective, raw):
        provenance = build_review_provenance(review, content, [], REQUEST, clean=True)
        assert provenance["model_output"] == review
        saved = {**complete_design_critique(review, content, evidence=[], review_request=REQUEST),
                 "model_review_provenance": provenance}
        trusted = _trusted_model_review(SimpleNamespace(content=content), SimpleNamespace(items=[]),
                                        SimpleNamespace(content=saved, provider_name="nvidia"), REQUEST)
        assert trusted == review


def test_critic_selects_frozen_references_without_reauthoring_identity_or_quotes():
    import json
    from app.design_agent.llm_provider import CompletionResult

    content = governed_artifact()
    original = copy.deepcopy(content)
    evidence = [{"chunk_id": "frozen-source", "content": "Mira advises the player at the mountain pass.",
                 "matched_sections": ["npc_archetypes"]}]
    wire = {"review_mode": "defect_detection", "summary": "Inspect this spoken claim.",
            "source_coverage": {section: "covered" for section in content}, "findings": [{
                "severity": "high", "issue": "This spoken claim needs human review.", "recommendation": "Compare its meaning with the source.",
                "reference": {"artifact_path": "/npc_archetypes/content/npcs/0/dialogue_triggers/0/text", "evidence_index": 0}}]}
    class Capture:
        def complete(self, request):
            self.request = request
            return CompletionResult(content=request.response_model.model_validate(wire).model_dump(), provider_name="nvidia", model_name="test")
    capture = Capture()
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, evidence, review_request=REQUEST)
    finding = result.metadata["finding_review_provenance"]["model_output"]["findings"][0]
    assert finding["section"] == "npc_archetypes" and finding["severity"] == "high"
    assert finding["issue"] == "This spoken claim needs human review."
    assert finding["reference"] == {"artifact_path": wire["findings"][0]["reference"]["artifact_path"],
        "artifact_value": "Your work at the pass is not yet finished.", "evidence_chunk_id": "frozen-source",
        "evidence_quote": "Mira advises the player at the mountain pass."}
    record_wire = copy.deepcopy(wire)
    record_wire["findings"][0]["reference"]["artifact_path"] = "/npc_archetypes/content/npcs/0/dialogue_triggers/0"
    record = capture.request.response_model.model_validate(record_wire).as_critique(content, evidence)
    assert record["findings"][0]["reference"]["artifact_value"] == content["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]
    for invalid in (-1, 1, True):
        bad = copy.deepcopy(wire)
        bad["findings"][0]["reference"]["evidence_index"] = invalid
        with pytest.raises(ValidationError):
            capture.request.response_model.model_validate(bad)
    for field, value in (("evidence_quote", "Invented GDD quote"), ("artifact_value", "Forged current value")):
        bad = copy.deepcopy(wire)
        bad["findings"][0]["reference"][field] = value
        with pytest.raises(ValidationError):
            capture.request.response_model.model_validate(bad)
    from app.design_agent.contracts import section_critique_response_model
    with pytest.raises(ValueError, match="non-empty"):
        section_critique_response_model(content, [{"chunk_id": "source", "content": "  "}])
    assert content == original


def test_section_critic_requires_cited_omission_findings_and_derives_a_consistent_verdict():
    from app.design_agent.contracts import section_critique_response_model

    content = governed_artifact()
    evidence = [{"chunk_id": "source", "content": "A mountain conflict."}]
    wire = {"review_mode": "defect_detection", "summary": "Source premise omitted.",
            "source_coverage": {section: "covered" for section in content}, "findings": [{
        "severity": "high", "issue": "Source premise omitted.",
        "recommendation": "Compare the description with the frozen source.", "reference": {
            "artifact_path": "/summary/content/description", "evidence_index": 0}}]}
    wire["source_coverage"]["summary"] = "missing"
    original = copy.deepcopy(wire)
    model = section_critique_response_model(content, evidence)
    parsed = model.model_validate(wire)
    canonical = parsed.as_critique(content, evidence)
    assert canonical["verdict"] == "needs_revision" and canonical["source_coverage"]["summary"] == "missing"
    expected = copy.deepcopy(wire["findings"])
    expected[0]["section"] = "summary"
    expected[0]["reference"].pop("evidence_index")
    expected[0]["reference"].update(evidence_chunk_id="source", evidence_quote="A mountain conflict.")
    expected[0]["reference"]["artifact_value"] = content["summary"]["content"]["description"]
    assert canonical["findings"] == expected
    assert "verdict" not in model.model_json_schema()["properties"]
    for fault in ("empty", "uncited", "blank_quote", "cross_section", "verdict"):
        invalid = copy.deepcopy(wire)
        if fault == "empty":
            invalid["findings"] = []
        elif fault == "uncited":
            invalid["findings"][0]["reference"]["evidence_index"] = None
        elif fault == "blank_quote":
            invalid["findings"][0]["reference"]["evidence_index"] = "   "
        elif fault == "cross_section":
            invalid["findings"][0]["reference"]["artifact_path"] = "/npc_archetypes/content/npcs"
        else:
            invalid["verdict"] = "ready_for_review"
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
    assert wire == original


def test_section_critic_cannot_certify_empty_shells_as_covered():
    from app.design_agent.contracts import section_critique_response_model

    content = governed_artifact()
    wire = {"review_mode": "defect_detection", "summary": "Controlled coverage check.",
            "source_coverage": {section: "covered" for section in content}, "findings": []}
    original = copy.deepcopy(content)
    for empty in (None, "  ", [], {}, {"description": None}, {"rules": []},
                  {"confidence": "High", "warnings": ["Claimed complete"], "citations": ["source"]}):
        candidate = copy.deepcopy(content)
        candidate["summary"]["content"] = empty
        model = section_critique_response_model(candidate, [])
        with pytest.raises(ValidationError):
            model.model_validate(wire)
        unknown = copy.deepcopy(wire)
        unknown["source_coverage"]["summary"] = "not_specified"
        assert model.model_validate(unknown).as_critique(candidate, [])["source_coverage"]["summary"] == "not_specified"
    # Explicit zero/false settings are content, not empty shells or semantic approval.
    for setting in (0, False):
        candidate = copy.deepcopy(content)
        candidate["summary"]["content"] = {"setting": setting}
        assert section_critique_response_model(candidate, []).model_validate(wire)
    assert content == original


def test_section_critic_references_paths_without_echoing_or_trusting_copied_values():
    import json
    from app.design_agent.contracts import section_critique_response_model

    content = governed_artifact()
    content["summary"]["content"]["a/b~c"] = ["Long authored text " * 50]
    original = copy.deepcopy(content)
    model = section_critique_response_model(content, [])
    assert '"artifact_value"' not in json.dumps(model.model_json_schema())
    reference = {"artifact_path": "/summary/content/a~1b~0c", "evidence_index": None}
    wire = {"review_mode": "defect_detection", "summary": "Inspect the authored note.",
            "source_coverage": {section: "covered" for section in content}, "findings": []}
    wire["findings"] = [{"severity": "medium",
        "issue": "Authored note needs review.", "recommendation": "Check its usefulness.", "reference": reference}]
    parsed = model.model_validate(wire)
    canonical = parsed.as_critique(content, [])
    assert canonical["findings"][0]["reference"]["artifact_value"] == content["summary"]["content"]["a/b~c"]
    canonical["findings"][0]["reference"]["artifact_value"].append("Detached result")
    assert content == original and "artifact_value" not in reference
    reference["artifact_value"] = "Forged value"
    with pytest.raises(ValidationError):
        model.model_validate(wire)
    reference.pop("artifact_value")
    reference["artifact_path"] = "/summary/content/missing"
    with pytest.raises(ValidationError):
        model.model_validate(wire)


@pytest.mark.parametrize("fault", ["missing_findings", "empty_covered"])
def test_section_critic_never_fabricates_missing_findings_after_bounded_reask(fault):
    import json
    import httpx
    from app.design_agent.contracts import section_critique_response_model
    from app.design_agent.llm_provider import CompletionRequest, NvidiaProvider, NvidiaStructuredOutputError
    from test_design_agent_llm_provider import _completion

    content = governed_artifact()
    wire = {"review_mode": "defect_detection", "summary": "Omitted premise.",
            "source_coverage": {section: "covered" for section in content}, "findings": []}
    if fault == "missing_findings":
        wire["source_coverage"]["summary"] = "missing"
    else:
        content["summary"]["content"] = {"description": None}
    calls = []
    def respond(request):
        calls.append(request)
        return _completion(json.dumps(wire))
    provider = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=True,
        key_reader=lambda _: "fake-test-key", sleep=lambda _: None,
        client=httpx.Client(transport=httpx.MockTransport(respond)))
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        provider.complete(CompletionRequest(node_name="critique", messages=[], response_model=section_critique_response_model(content, [])))
    assert len(calls) == (2 if fault == "missing_findings" else 1)
    assert caught.value.code == "structured_output_invalid"
    if fault == "missing_findings":
        assert caught.value.diagnostics["source_omission_reask"] == "failed"


@pytest.mark.parametrize("cause,blocked", [
    ("Fewer than 5 chunks of raw sky-iron ore extracted from cliffside veins", True),
    ("Fewer than 5 chunks of raw sky-iron ore extracted from cliffside veins after the deadline", False),
    ("Not fewer than 5 chunks of raw sky-iron ore extracted from cliffside veins", False),
])
def test_saved_fewer_ore_failure_is_not_confused_with_a_separate_deadline(cause, blocked):
    content = governed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest["failure_states"] = [cause]
    event = quest["state_contract"]["failure"]["events"][0]
    quest["state_contract"]["event_actions"][event] = cause
    critique = complete_design_critique({"review_mode": "defect_detection", "summary": "No model findings.",
        "findings": [], "verdict": "ready_for_review"}, content, review_request=REQUEST)
    gaps = critique["quality_scorecard"]["request_coverage_gaps"]
    assert any(gap["code"] == "quest_failure_predicate" for gap in gaps) is blocked
    if blocked:
        assert critique["verdict"] == "needs_revision"


def test_empty_section_critic_cannot_hide_known_quest_and_dialogue_defects():
    from app.design_agent.grounding import validate_design_approval

    content = governed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest["failure_states"] = ["Guards remain alive", "Northern flag not raised"]
    quest["state_contract"]["failure"]["events"] = ["guards_alive", "flag_not_raised"]
    quest["state_contract"]["event_actions"].update(guards_alive="Guards remain alive", flag_not_raised="Northern flag not raised")
    second = copy.deepcopy(quest)
    second.update(id="quest_2", title="Mine ore", failure_states=["Less than 5 chunks of raw ore mined"])
    second["state_contract"]["failure"]["events"] = ["not_enough_ore"]
    second["state_contract"]["event_actions"]["not_enough_ore"] = "Less than 5 chunks of raw ore mined"
    content["quest_hooks"]["content"]["quests"].append(second)
    for record in (quest, second):
        contract = record["state_contract"]
        declared = {item["event"] for item in contract["objectives"]} | set(contract["failure"]["events"])
        if contract["restart"]:
            declared.add(contract["restart"]["event"])
        contract["event_actions"] = {key: value for key, value in contract["event_actions"].items() if key in declared}
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    mapping = copy.deepcopy(npc["dialogue_triggers"][0])
    npc["dialogue_triggers"] = [{**copy.deepcopy(mapping), "trigger": f"progress_{index}", "situation": situation}
                                for index, situation in enumerate(("greeting", "quest_offer", "greeting"))]
    content["npc_archetypes"]["content"]["npcs"].append({**copy.deepcopy(npc), "name": "Second advisor"})
    wire = {"review_mode": "defect_detection", "summary": "No model findings.",
            "sections": {section: {"coverage": "covered", "findings": []} for section in content}}
    result = NvidiaDesignAgentProvider(llm_provider=BlueprintCapturingProvider(wire)).critique(content, [], review_request=REQUEST)
    assert result.metadata["finding_review_provenance"]["model_output"]["findings"] == []
    gaps = result.content["quality_scorecard"]["request_coverage_gaps"]
    assert sum(gap["code"] == "quest_failure_predicate" for gap in gaps) == 3
    assert sum(gap["code"] == "dialogue_stage_situation" for gap in gaps) == 6
    assert result.content["verdict"] == "needs_revision"
    with pytest.raises(ValueError):
        validate_design_approval(content, [], result.content, review_request=REQUEST)


def test_governed_prompts_are_concise_design_instructions_not_copied_checklists():
    import json
    content = governed_artifact()
    request = {**REQUEST, "objective": "Provide three useful lines with a quest", "fresh_dialogue": True,
               "dialogue_policy": "Repeat only while eligible", "defer_runtime": True}
    capture = BlueprintCapturingProvider(content)
    provider = NvidiaDesignAgentProvider(llm_provider=capture)
    provider.generate(request, [])
    prompt = capture.requests[-1].messages[1]["content"]
    task = prompt.split("Task: ", 1)[1].split("JSON Schema:", 1)[0].split("\nInput:", 1)[0]
    payload = json.loads(prompt.split("Input: ", 1)[1])
    assert len(task.split()) < 450
    assert prompt.count(request["objective"]) == 1
    assert "review targets" not in task.lower()
    assert "do not copy the human request" in task.lower()
    assert "add no return/delivery/hand-in requirements through speech, hooks or notes" in task.lower()
    assert "manual_test" in task and "completion_action" in task and "quest_index" in task
    assert "state_contract.event_actions" not in task
    assert "plan" not in payload and "resolved_decisions" in payload
    capture = BlueprintCapturingProvider({"review_mode": "defect_detection", "verdict": "ready_for_review", "findings": [], "summary": "Capture only",
        "source_coverage": {section: "deferred" if section == "unity_runtime_preview" else "covered" for section in content}})
    NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [], review_request=request)
    prompt = capture.requests[-1].messages[1]["content"]
    task = prompt.split("Task: ", 1)[1].split("JSON Schema:", 1)[0].split("\nInput:", 1)[0]
    payload = json.loads(prompt.split("Input: ", 1)[1])
    assert len(task.split()) < 350 and prompt.count(request["objective"]) == 1
    assert "greetings may be quest-scoped" in task.lower()
    assert "source_coverage entry" in task and "not_specified" in task and "pending confirmation alone is not a defect" in task.lower()
    assert "not source presence" in task and "server attaches exact values" in task.lower()
    assert "recommend verification, not replacement text" in task.lower()
    assert "failure_states are readable summaries, not event ids" in task.lower()
    assert "event_actions" in task and "pending_proposals" not in payload["review_context"]
    assert "full required total is valid" in task and "single event is not necessarily per-item" in task
    assert "quantity or required actions still missing" in task and "not an imagined implementation" in task
    assert "unfinished objective alone is not failure" in task
    assert "greeting labels require greeting stage" in task.lower()
    assert payload["artifact"] == {name: {key: value for key, value in section.items()
                                         if key != "confidence"}
                                   for name, section in content.items()}
    assert list(payload) == ["evidence", "artifact", "review_context"]
    schema = json.dumps(capture.requests[-1].response_model.model_json_schema())
    assert "/npc_archetypes/content/npcs/0/dialogue_style" in schema
    assert "/npc_archetypes/content/npcs[0]/dialogue_style" not in schema
    # Existing human requirements remain prominent and verbatim, not folded into evidence.
    assert json.dumps(request["dialogue_policy"]) in prompt.split("Task: ", 1)[0]


@pytest.mark.parametrize("scoped", [False, True])
def test_grounded_generation_contract_uses_exact_section_ids_and_preserves_input(scoped):
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, grounded_response_model

    content = governed_artifact()
    for section in content.values():
        section["citations"] = ["source-a"]
    for key, records in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
        for record in content[key]["content"][records]:
            record["source_chunk_ids"] = ["source-a"]
    evidence = [{"chunk_id": "source-a", "matched_sections": list(BLUEPRINT_SECTION_KEYS)},
                {"chunk_id": "summary-only", "matched_sections": ["summary"]}]
    original, original_evidence = copy.deepcopy(content), copy.deepcopy(evidence)
    contract = (revision_response_model(["npc_archetypes", "quest_hooks"], generated=True, design_contract_version=2)
                if scoped else GeneratedGovernedBlueprintContent)
    model = grounded_response_model(contract, evidence)
    selected = {key: content[key] for key in contract.model_fields}
    assert model.model_validate(selected)
    schema = model.model_json_schema()
    section_schema = schema["$defs"]["GroundedQuestHooks"]
    assert section_schema["properties"]["citations"]["items"] == {"const": "source-a", "type": "string"}
    assert schema["$defs"]["GroundedGeneratedGovernedQuestContent"]["properties"]["quests"]["maxItems"] == 2
    npc_schema = schema["$defs"]["GroundedFreshGovernedNPC"]
    assert npc_schema["properties"]["source_chunk_ids"]["items"] == {"const": "source-a", "type": "string"}
    for bad in ('/chunk_id="source-a"', "summary-only", "unknown-source"):
        invalid = copy.deepcopy(selected)
        invalid["quest_hooks"]["citations"] = [bad]
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
        invalid = copy.deepcopy(selected)
        invalid["npc_archetypes"]["content"]["npcs"][0]["source_chunk_ids"] = [bad]
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
    assert content == original and evidence == original_evidence
    assert GeneratedGovernedBlueprintContent.model_validate(original)  # Historical schema unchanged.


@pytest.mark.parametrize("scoped", [False, True])
def test_grounded_wire_requires_citations_for_content_but_allows_uncited_empty_sections(scoped):
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, grounded_response_model
    evidence = [{"chunk_id": "source", "matched_sections": list(BLUEPRINT_SECTION_KEYS)}]
    content = governed_artifact()
    for section in content.values():
        section["citations"] = ["source"]
    for section, records in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
        for record in content[section]["content"][records]:
            record["source_chunk_ids"] = ["source"]
    contract = revision_response_model(["summary"], generated=True, design_contract_version=2) if scoped else ContentBlueprintDraft
    selected = {"summary": content["summary"]} if scoped else content_draft_fixture(content)
    original = copy.deepcopy(selected)
    model = grounded_response_model(contract, evidence)
    assert model.model_validate(selected)
    for citations in ([], ["unknown"]):
        invalid = copy.deepcopy(selected)
        invalid["summary"]["citations"] = citations
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
    invalid["summary"].pop("citations")
    with pytest.raises(ValidationError):
        model.model_validate(invalid)
    if scoped:
        for value in (False, 0, "Design text", ["Design text"], {"description": "Design text"}):
            invalid["summary"].update(content={"design": value}, citations=[])
            with pytest.raises(ValidationError):
                model.model_validate(invalid)
    empty = copy.deepcopy(selected)
    empty["summary"].update(content={} if scoped else {"description": None}, citations=[], warnings=["Missing design input"])
    assert model.model_validate(empty)
    schema = model.model_json_schema()["$defs"]["GroundedSummary"]
    assert "citations" in schema["required"]
    assert schema["anyOf"][0]["properties"]["citations"]["minItems"] == 1
    assert schema["anyOf"][1]["properties"]["citations"]["maxItems"] == 0
    assert all(set(branch["properties"]) == set(schema["properties"]) for branch in schema["anyOf"])
    assert "propertyNames" not in str(schema)
    assert selected == original


def test_citation_only_revision_requires_a_real_frozen_evidence_repair():
    from app.design_agent.grounding import validate_structured_revision
    before = governed_artifact()
    before["summary"]["citations"] = []
    after = copy.deepcopy(before)
    after["summary"]["citations"] = ["summary-source"]
    evidence = [{"chunk_id": "summary-source", "matched_sections": ["summary"]},
                {"chunk_id": "other-source", "matched_sections": ["summary"]}]
    assert validate_structured_revision(before, after, "Add the missing summary citation", target_sections=["summary"], evidence=evidence) == "summary"
    before["summary"]["citations"] = ["invalid-old-source"]
    assert validate_structured_revision(before, after, "Correct the summary citation", target_sections=["summary"], evidence=evidence) == "summary"
    with pytest.raises(ValueError, match="did not materially change"):
        validate_structured_revision(before, after, "Add a citation", target_sections=["summary"])
    for invalid in (["foreign"], ["summary-source", "foreign"]):
        after["summary"]["citations"] = invalid
        with pytest.raises(ValueError, match="did not materially change"):
            validate_structured_revision(before, after, "Correct the summary", target_sections=["summary"], evidence=evidence)
    before["summary"]["citations"] = ["summary-source"]
    after["summary"]["citations"] = ["other-source"]
    with pytest.raises(ValueError, match="did not materially change"):
        validate_structured_revision(before, after, "Correct the summary", target_sections=["summary"], evidence=evidence)

    for empty in ({}, {"description": None}, {"description": " \n "}):
        before["summary"].update(content=empty, citations=[])
        after = copy.deepcopy(before)
        after["summary"]["citations"] = ["summary-source"]
        with pytest.raises(ValueError, match="unchanged: summary"):
            validate_structured_revision(before, after, "Populate the missing summary", target_sections=["summary"], evidence=evidence)
    after["summary"]["content"] = {"description": "A source-backed game premise."}
    assert validate_structured_revision(before, after, "Populate the missing summary", target_sections=["summary"], evidence=evidence) == "summary"


def test_grounded_scope_rejects_unsupported_records_and_deferred_runtime_claims():
    from app.design_agent.contracts import grounded_response_model

    model = grounded_response_model(GeneratedGovernedBlueprintContent,
                                   [{"chunk_id": "source", "matched_sections": ["summary", "quest_hooks"]}],
                                   defer_runtime=True)
    content = governed_artifact()
    for key, section in content.items():
        section["citations"] = ["source"] if key in ("summary", "quest_hooks") else []
        if key not in ("summary", "quest_hooks", "npc_archetypes"):
            section["content"] = {}
    content["npc_archetypes"]["content"]["npcs"] = []
    content["unity_runtime_preview"]["content"] = {}
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest["source_chunk_ids"] = ["source"]
    assert model.model_validate(content)
    for mutate in (
        lambda c: c["unity_runtime_preview"].update(content={"integration_notes": "Not defined"}),
        lambda c: c["unity_runtime_preview"].update(citations=["source"]),
        lambda c: c["gameplay_systems"].update(content={"systems": [{"description": "Uncited mechanic"}]}),
        lambda c: c["npc_archetypes"]["content"].update(npcs=governed_artifact()["npc_archetypes"]["content"]["npcs"]),
        lambda c: c["quest_hooks"]["content"]["quests"][0].update(runtime={"npc_slug": "mira", "difficulty": "easy",
                    "gold_reward": 0, "xp_reward": 0, "objectives": [{"description": "Clear guards", "target_type": "enemy", "target_id": "guards", "quantity_required": 1}]}),
    ):
        invalid = copy.deepcopy(content)
        mutate(invalid)
        with pytest.raises(ValidationError):
            model.model_validate(invalid)


@pytest.mark.parametrize("guided", [False, True])
def test_adapter_applies_citation_contract_to_generation_and_revision_wire(guided, monkeypatch):
    import json
    import httpx
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from app.design_agent.llm_provider import NvidiaProvider
    from test_design_agent_llm_provider import _completion

    monkeypatch.setenv("NVIDIA_GUIDED_JSON_ENABLED", str(guided).lower())
    content = governed_artifact()
    for section in content.values():
        section["citations"] = ["source"]
    for key, records in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
        for record in content[key]["content"][records]:
            record["source_chunk_ids"] = ["source"]
    evidence = [{"chunk_id": "source", "content": "Mira guards the pass.", "matched_sections": list(BLUEPRINT_SECTION_KEYS)}]
    calls = []
    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        schema = payload["response_format"]["json_schema"]["schema"] if guided else json.loads(payload["messages"][1]["content"].split("JSON Schema: ", 1)[1].split("\n", 1)[0])
        if len(calls) == 1:
            assert '"const": "S0"' in json.dumps(schema)
            for field in schema["properties"].values():
                section = schema["$defs"][field["$ref"].rsplit("/", 1)[1]]
                assert "citations" in section["required"]
                assert section["anyOf"][0]["properties"]["citations"]["minItems"] == 1
                assert section["anyOf"][1]["properties"]["citations"]["maxItems"] == 0
            wire = copy.deepcopy(content)
            for section in wire.values():
                section["citations"] = ["S0"]
                for key in ("npcs", "quests"):
                    for record in section["content"].get(key, []):
                        record["source_chunk_ids"] = ["S0"]
            fixture = content_draft_fixture(wire)
        else:
            assert set(schema["properties"]) == {"changes"}
            fixture = {"changes": [{"artifact_path": "/quest_hooks/citations", "replacement": ["source"]}]}
        output = {key: fixture[key] for key in schema["properties"]}
        return _completion(json.dumps(output))
    transport = NvidiaProvider(base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=False,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond)))
    adapter = NvidiaDesignAgentProvider(llm_provider=transport)
    result = adapter.generate(REQUEST, evidence)
    assert result.metadata["generation_contract"] == "content_first_v2"
    assert all(section["citations"] == ["source"] for section in result.content.values())
    content = copy.deepcopy(result.content)  # Revision operates on the assembled stored shape.
    revised = adapter.revise(result.content, evidence, "Recheck objective events", target_sections=["quest_hooks"], review_request=REQUEST)
    assert len(calls) == 2 and revised.content["npc_archetypes"] == result.content["npc_archetypes"]
    for call in calls[:1]:
        task = call["messages"][1]["content"]
        assert "Keep greeting stage even when quest-scoped" in task
        assert "Quest offers need explicit availability" in task
        assert "Split independently required player actions" in task
        assert "never once per item" in task
        assert "fresh_dialogue controls novelty, not whether speech is included" in task
        assert "explicit player actions in quests" in task
        assert "Preserve source numerals verbatim" in task
    generation_task = calls[0]["messages"][1]["content"]
    assert "zero-based index of a returned quest" in generation_task
    assert "server derives quest IDs, flags and state bookkeeping" in generation_task
    assert "Never treat an unfinished objective as failure" in generation_task
    assert "failure_states empty" in generation_task
    revision_task = calls[1]["messages"][1]["content"]
    assert "copy existing quest id and dialogue trigger selectors exactly" in revision_task
    assert "Omit eligibility, state_contract, flags" in revision_task
    assert "server preserves identities and assembles bookkeeping" in revision_task
    assert "quest_state_context when quests are unselected" in revision_task


def test_grounded_generation_keeps_existing_syntax_recovery_without_repairing_content():
    import json
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, grounded_response_model
    from test_json_closer_recovery import invoke

    content = governed_artifact()
    source_id = content["quest_hooks"]["citations"][0]
    evidence = [{"chunk_id": source_id, "matched_sections": list(BLUEPRINT_SECTION_KEYS)}]
    model = grounded_response_model(GeneratedGovernedBlueprintContent, evidence)
    result, calls = invoke(json.dumps(content)[:-1], model=model)
    assert len(calls) == 1 and result.metadata["local_recovery"]
    assert result.metadata["recovery_requires_review"] and result.metadata["repair_attempts"] == 0
    assert result.content == model.model_validate(content).model_dump()


def test_governed_quantity_cannot_disappear_from_objective_or_completion_action():
    from app.design_agent.grounding import validate_design_approval

    content = governed_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    quest.update(title="Mine 5 chunks of raw sky-iron ore",
                 objective="Mine 5 chunks of raw sky-iron ore from the cliffside veins.",
                 objectives=["Mine sky-iron ore"], failure_states=["Player is defeated"], implementation_notes=[])
    quest["state_contract"] = {
        "version": "1", "objectives": [{"objective": "Mine sky-iron ore", "flag": "ore_mined", "event": "ore_extract"}],
        "completion": {"required_flags": ["ore_mined"], "mode": "all", "reevaluate_on": "each_objective_update", "lifecycle": "completed"},
        "failure": {"events": ["player_defeated"], "lifecycle": "failed"}, "restart": None,
        "event_actions": {"ore_extract": "sky-iron ore chunk removed from vein", "player_defeated": "Player health reaches zero"},
    }
    original = copy.deepcopy(content)
    ready = {"verdict": "ready_for_review", "summary": "Model missed the count", "findings": []}
    score = assess_artifact_quality(content, review_request=REQUEST)
    assert "quest_quantity_coverage" in {gap["code"] for gap in score["request_coverage_gaps"]}
    reviewed = complete_design_critique(ready, content, review_request=REQUEST)
    assert reviewed["verdict"] == "needs_revision"
    with pytest.raises(ValueError, match="Request coverage"):
        validate_design_approval(content, [], ready, review_request=REQUEST)
    assert content == original
    quest["implementation_notes"].append("Complete only after 5 chunks")
    assert "quest_quantity_coverage" in {g["code"] for g in assess_artifact_quality(content, review_request=REQUEST)["request_coverage_gaps"]}
    quest["objectives"] = ["Mine 5 chunks of raw sky-iron ore"]
    quest["state_contract"]["objectives"][0]["objective"] = quest["objectives"][0]
    assert "quest_quantity_coverage" in {g["code"] for g in assess_artifact_quality(content, review_request=REQUEST)["request_coverage_gaps"]}
    quest["state_contract"]["event_actions"]["ore_extract"] = "Player's collected sky-iron total reaches 5 chunks; not a per-chunk event"
    assert "quest_quantity_coverage" not in {g["code"] for g in assess_artifact_quality(content, review_request=REQUEST)["request_coverage_gaps"]}
    assert assess_artifact_quality(original)["request_coverage_gaps"] == []  # No retroactive legacy parsing.
    assert ready["findings"] == []


def test_governed_revision_keeps_scope_and_locked_policy_in_concise_prompt():
    content = governed_artifact()
    before = copy.deepcopy(content)
    capture = BlueprintCapturingProvider(content)
    request = {**REQUEST, "fresh_dialogue": True, "dialogue_policy": "Repeat only while eligible"}
    result = NvidiaDesignAgentProvider(llm_provider=capture).revise(content, [], "Make dialogue state-neutral",
        target_sections=["npc_archetypes"], review_request=request)
    prompt = capture.requests[-1].messages[1]["content"]
    assert "Make dialogue state-neutral" in prompt and request["dialogue_policy"] in prompt
    assert "revise only target_sections" in prompt.lower()
    assert "Correct every requested field" in prompt
    assert "Remove rejected prerequisites from actions, notes and assumptions" in prompt
    assert "Relabelling is not correction" in prompt
    assert "Compare the result with each requested correction" in prompt
    assert "Preserve all unmentioned data" in prompt
    assert result.content["quest_hooks"] == content["quest_hooks"]
    assert content == before


def test_governed_notes_reference_manual_checks_without_copying_spoken_text():
    content = governed_artifact()
    legacy = validate_generated_blueprint(content)
    before = copy.deepcopy(legacy)
    normalized = validate_generated_blueprint(legacy, design_contract_version=2)
    npc = normalized["npc_archetypes"]["content"]["npcs"][0]
    mapping = npc["dialogue_triggers"][0]
    assert mapping["text"] in mapping["manual_test"]
    assert all(mapping["text"] not in note for note in npc["implementation_notes"])
    assert any("manual_test" in note and "repeat_policy" in note for note in npc["implementation_notes"])
    assert legacy == before and normalized == validate_generated_blueprint(normalized, design_contract_version=2)
