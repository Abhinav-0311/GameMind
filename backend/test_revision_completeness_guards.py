"""Regressions for partial/cosmetic revisions and cited but empty designs."""
import copy
import uuid

import pytest

from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, BlueprintContent
from app.design_agent.grounding import assess_artifact_quality, complete_design_critique, validate_structured_revision


def complete_artifact(source_id="11111111-1111-1111-1111-111111111111"):
    content = {
        key: {"content": {"description": "A concrete design decision."},
              "citations": [source_id], "confidence": "High", "warnings": []}
        for key in BLUEPRINT_SECTION_KEYS
    }
    content["npc_archetypes"]["content"] = {"npcs": [{
        "name": "Mira", "archetype": "Mentor", "dialogue_style": "Brief warnings",
        "dialogue_hooks": ["Check the route before moving."], "source_chunk_ids": [source_id],
        "implementation_notes": ["On threat entry, show the warning before enabling movement."],
    }]}
    content["quest_hooks"]["content"] = {"quests": [{
        "id": "training", "title": "Training Sandbox", "objective": "Learn core mechanics.",
        "objectives": ["Unlock weak\u2011password gate"],
        "failure_states": ["Fail to complete mission within time limit"],
        "dialogue_hooks": ["PATCH teaches core mechanics."], "source_chunk_ids": [source_id],
        "implementation_notes": [
            "Proposal - Objective: Unlock weak-password gate; Event: Insert the correct authentication token; "
            "State: Gate objective changes from pending to complete; Check: The gate is open and its objective is complete."
        ],
    }]}
    return BlueprintContent.model_validate(content).model_dump()


def metric(scorecard, key):
    return next(item for item in scorecard["metrics"] if item["key"] == key)


def test_quest_integration_requires_a_complete_check_for_each_objective():
    from app.design_agent.grounding import validate_design_approval

    content = complete_artifact()
    quest = content["quest_hooks"]["content"]["quests"][0]
    before = copy.deepcopy(content)
    assert metric(assess_artifact_quality(content), "integration_readiness")["passed"]
    valid_note = quest["implementation_notes"][0]
    for notes in (["Map objectives to game events."],
                  [valid_note.replace("Objective: Unlock weak-password gate", "Objective: Enter training")],
                  [valid_note.replace("Event: Insert the correct authentication token", "Event: ")],
                  [valid_note.replace("State: Gate objective changes from pending to complete", "State: ")],
                  [valid_note.replace("Check: The gate is open and its objective is complete.", "Check: ")],
                  [valid_note.replace("Check: The gate is open and its objective is complete.", "Check: <observable result>")]):
        quest["implementation_notes"] = notes
        score = assess_artifact_quality(content)
        assert not metric(score, "integration_readiness")["passed"]
        assert score["quest_integration_gaps"] == [{"record_id": "training", "record": "Training Sandbox",
                                                   "objectives": quest["objectives"]}]
        assert "Training Sandbox" in metric(score, "integration_readiness")["detail"]
        with pytest.raises(ValueError, match="Integration readiness"):
            validate_design_approval(content, [], {"verdict": "ready_for_review", "findings": [],
                                                   "quality_scorecard": {"passed": True, "blockers": []}})
    quest["implementation_notes"] = [valid_note]
    quest["objectives"].append("Inspect the suspicious link.")
    assert assess_artifact_quality(content)["quest_integration_gaps"][0]["objectives"] == ["Inspect the suspicious link."]
    quest["objectives"][-1] = quest["objectives"][0]  # One note cannot cover duplicate objectives.
    assert assess_artifact_quality(content)["quest_integration_gaps"]
    assert assess_artifact_quality(before)["quest_integration_gaps"] == []


@pytest.mark.parametrize("cosmetic", ["unchanged", "hyphen", "whitespace", "case", "notes_removed", "metadata"])
def test_each_selected_section_must_change_not_just_npc_dialogue(cosmetic):
    before = complete_artifact()
    after = copy.deepcopy(before)
    after["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] = ["Inspect that suspicious link before opening it."]
    quest = after["quest_hooks"]["content"]["quests"][0]
    if cosmetic == "hyphen":
        quest["objectives"] = ["Unlock weak-password gate"]
    elif cosmetic == "whitespace":
        quest["objective"] = "  Learn   core mechanics.  "
    elif cosmetic == "case":
        quest["objective"] = "LEARN CORE MECHANICS."
    elif cosmetic == "notes_removed":
        quest["implementation_notes"] = []
    elif cosmetic == "metadata":
        quest["assumptions"] = ["Revised as requested."]
        after["quest_hooks"]["warnings"] = ["Timer removed."]
    with pytest.raises(ValueError, match="did not materially change.*quest_hooks"):
        validate_structured_revision(before, after, "Improve dialogue and remove the invented quest timer.",
                                     target_sections=["npc_archetypes", "quest_hooks"])


def test_live_qa_combined_cosmetic_changes_cannot_hide_retained_timer():
    before = complete_artifact()
    after = copy.deepcopy(before)
    after["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] = ["Inspect the link before clicking."]
    quest = after["quest_hooks"]["content"]["quests"][0]
    quest["objectives"] = ["Unlock weak-password gate"]
    quest["implementation_notes"] = [
        "Use 'training' as the stable design key and map objectives in their listed order to game events.",
        "Map failure states to explicit quest-state transitions; do not infer rewards or prerequisites from assumptions.",
        "Do not implement listed assumptions until a designer confirms them.",
    ]
    with pytest.raises(ValueError, match="did not materially change.*quest_hooks"):
        validate_structured_revision(before, after, "Correct both sections.",
                                     target_sections=["npc_archetypes", "quest_hooks"])


def test_corrected_dialogue_and_timer_are_valid_scoped_revision():
    before = complete_artifact()
    after = copy.deepcopy(before)
    after["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] = ["Inspect the link before clicking."]
    after["quest_hooks"]["content"]["quests"][0]["failure_states"] = ["Leave training before completing the mission."]
    assert validate_structured_revision(before, after, "Correct both sections.",
                                        target_sections=["npc_archetypes", "quest_hooks"]) == "npc_archetypes,quest_hooks"


def test_genuine_new_integration_step_is_a_material_revision():
    before = complete_artifact()
    after = copy.deepcopy(before)
    after["quest_hooks"]["content"]["quests"][0]["implementation_notes"] = [
        "On correct token insertion, mark the gate objective complete and open the gate."
    ]
    assert validate_structured_revision(before, after, "Add concrete quest integration steps.",
                                        target_sections=["quest_hooks"]) == "quest_hooks"


def test_notes_only_removal_preserves_every_other_field_and_remains_reviewable():
    from app.design_agent.grounding import validate_design_approval

    before = complete_artifact()
    rejected = {
        "npc_archetypes": ("npcs", "Scene integration proposal: Place Eldrin in the Watchtower interior, accessible after initial tutorial."),
        "quest_hooks": ("quests", "Scene integration proposal: Place Ash Pass in the Geothermal Vents zone, accessible after leaving Watchtower."),
    }
    for section, (collection, note) in rejected.items():
        before[section]["content"][collection][0]["implementation_notes"].append(note)
    after = copy.deepcopy(before)
    for section, (collection, note) in rejected.items():
        after[section]["content"][collection][0]["implementation_notes"].remove(note)

    original = copy.deepcopy(before)
    assert validate_structured_revision(
        before, after, "Remove the two rejected scene integration notes only; preserve all other fields.",
        target_sections=list(rejected),
    ) == "npc_archetypes,quest_hooks"
    assert before == original
    restored = copy.deepcopy(after)
    for section, (collection, note) in rejected.items():
        restored[section]["content"][collection][0]["implementation_notes"].append(note)
    assert restored == before
    # A material correction is not an acceptance or approval verdict.
    with pytest.raises(ValueError, match="Independent critique must be resolved"):
        validate_design_approval(after, [], {
            "verdict": "needs_revision", "findings": [{
                "severity": "high", "section": "quest_hooks",
                "issue": "Other content still requires review.", "recommendation": "Review the remaining design.",
            }], "summary": "Still blocked.",
        })


@pytest.mark.parametrize("change", ["unchanged_target", "boilerplate_only", "unselected_section", "metadata_drift"])
def test_notes_only_removal_does_not_bypass_scope_or_material_change_guards(change):
    before = complete_artifact()
    generated_note = "Do not implement listed assumptions until a designer confirms them."
    before["quest_hooks"]["content"]["quests"][0]["implementation_notes"].append(generated_note)
    after = copy.deepcopy(before)
    npc = after["npc_archetypes"]["content"]["npcs"][0]
    quest = after["quest_hooks"]["content"]["quests"][0]
    npc["implementation_notes"] = []
    targets = ["npc_archetypes", "quest_hooks"]
    if change == "boilerplate_only":
        quest["implementation_notes"].remove(generated_note)
    elif change == "unselected_section":
        targets = ["quest_hooks"]
        quest["implementation_notes"] = []
    elif change == "metadata_drift":
        quest["implementation_notes"] = []
        after["npc_archetypes"]["warnings"].append("Changed outside implementation notes.")
    with pytest.raises(ValueError, match="unchanged: .*quest_hooks|changed unrelated sections: npc_archetypes"):
        validate_structured_revision(before, after, "Remove rejected integration notes only.", target_sections=targets)


@pytest.mark.parametrize("empty", [{}, {"notes": []}, {"description": " \n "},
                                  {"nested": {"items": [None, {}, [], " "]}},
                                  {"title": "Gameplay systems", "generation_mode": "nvidia"}])
def test_citations_do_not_make_empty_design_sections_complete(empty):
    content = complete_artifact()
    content["gameplay_systems"]["content"] = empty
    scorecard = assess_artifact_quality(content)
    assert metric(scorecard, "completeness")["passed"] is False
    assert metric(scorecard, "completeness")["value"] < 1.0
    assert "gameplay_systems" in scorecard["incomplete_sections"]
    assert "gameplay_systems" in metric(scorecard, "completeness")["detail"]
    assert metric(scorecard, "integration_readiness")["value"] == 0.0
    assert "Completeness" in scorecard["blockers"]


def test_live_qa_seven_empty_sections_are_not_one_hundred_percent_complete():
    content = complete_artifact()
    empty_sections = [key for key in BLUEPRINT_SECTION_KEYS if key not in {"npc_archetypes", "quest_hooks"}]
    for key in empty_sections:
        content[key]["content"] = {}
    # Sparse content remains a valid draft, but must not be called complete.
    BlueprintContent.model_validate(content)
    scorecard = assess_artifact_quality(content)
    assert metric(scorecard, "completeness")["value"] == round(2 / 9, 4)
    assert scorecard["incomplete_sections"] == empty_sections
    assert scorecard["passed"] is False


def test_critique_cannot_miss_empty_sections_or_silence_real_findings_as_proposals():
    content = complete_artifact()
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["assumptions"] = ["Proposal: a fresh warning once per mission attempt; reset on restart."]
    critic = {"verdict": "ready_for_review", "findings": [], "summary": "Independent review."}
    before = copy.deepcopy(content)
    proposal_review = complete_design_critique(critic, content)
    assert proposal_review["verdict"] == "ready_for_review"
    assert proposal_review["findings"] == []  # Pending confirmation is not a fabricated contradiction.
    assert proposal_review["quality_scorecard"]["blockers"] == ["Integration readiness"]
    assert content == before and critic["findings"] == []

    real_finding = {"severity": "high", "section": "npc_archetypes",
                    "issue": "The warning tells the player to run an untrusted executable.",
                    "recommendation": "Replace unsafe advice with the source-supported defensive action."}
    protected = complete_design_critique({**critic, "findings": [real_finding]}, content)
    assert protected["verdict"] == "needs_revision" and protected["findings"] == [real_finding]

    empty_sections = [key for key in BLUEPRINT_SECTION_KEYS if key not in {"npc_archetypes", "quest_hooks"}]
    for section in empty_sections:
        content[section]["content"] = {}
    result = complete_design_critique(critic, content)
    assert result["verdict"] == "needs_revision"
    assert {item["section"] for item in result["findings"]} == set(empty_sections)
    assert all(item["severity"] == "high" for item in result["findings"])
    assert complete_design_critique(result, content) == result  # Provider + workflow normalization is idempotent.


def test_complete_structured_design_without_invented_dependencies_passes():
    scorecard = assess_artifact_quality(complete_artifact())
    assert metric(scorecard, "completeness")["value"] == 1.0
    assert metric(scorecard, "completeness")["passed"] is True
    assert scorecard["incomplete_sections"] == []

    from pydantic import ValidationError
    from app.design_agent.contracts import ResumeDecision
    from app.design_agent.schemas import DesignAgentReviewRequest
    from app.design_agent.grounding import validate_design_approval, validate_generated_blueprint

    content = complete_artifact()
    content["quest_hooks"]["content"]["quests"][0]["failure_states"] = ["Leave training before completing the mission."]
    evidence = [{"chunk_id": content["summary"]["citations"][0],
                 "content": "Mira mentors the Training Sandbox. Learn core mechanics. Unlock weak-password gate.",
                 "matched_sections": list(BLUEPRINT_SECTION_KEYS)}]
    content = validate_generated_blueprint(content, evidence)
    before = copy.deepcopy(content)
    pending = assess_artifact_quality(content)["unresolved_assumptions"]
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")} for item in pending]
    critique = {"verdict": "ready_for_review", "findings": [], "quality_scorecard": assess_artifact_quality(content)}
    artifact_id = uuid.uuid4()
    request = DesignAgentReviewRequest(decision="approve", artifact_id=artifact_id,
                                       confirmed_proposals=confirmations)
    decision = ResumeDecision.model_validate(request.model_dump())
    decision.require_current_artifact(artifact_id)
    with pytest.raises(ValueError, match="current draft"):
        decision.require_current_artifact(uuid.uuid4())
    with pytest.raises(ValidationError):
        DesignAgentReviewRequest(decision="approve", confirmed_proposals=confirmations)
    with pytest.raises(ValidationError):
        DesignAgentReviewRequest(decision="reject", reason="Fix dialogue", target_sections=["npc_archetypes"],
                                 artifact_id=artifact_id, confirmed_proposals=confirmations)

    assert validate_design_approval(content, evidence, critique, confirmations)["passed"]
    assert content == before and critique["quality_scorecard"]["unresolved_assumptions"] == pending
    with pytest.raises(ValueError, match="Integration readiness"):
        validate_design_approval(content, evidence, critique, confirmations[:-1])
    for invalid in ([*confirmations, confirmations[0]],
                    [{**confirmations[0], "record_id": "another-record"}]):
        with pytest.raises(ValueError, match="confirmation"):
            assess_artifact_quality(content, invalid)
    for bad_critique in ({**critique, "verdict": "needs_revision"},
                         {**critique, "findings": [{"severity": "high"}]}, {}):
        with pytest.raises(ValueError, match="Independent critique"):
            validate_design_approval(content, evidence, bad_critique, confirmations)
    for fault in ("empty", "citation", "recovered", "timer", "notes"):
        broken = copy.deepcopy(content)
        if fault == "empty":
            broken["gameplay_systems"]["content"] = {}
        elif fault == "citation":
            broken["gameplay_systems"]["citations"] = ["outside-snapshot"]
        elif fault == "recovered":
            broken["gameplay_systems"]["warnings"] = ["The blueprint response required closing-delimiter recovery."]
        elif fault == "notes":
            broken["npc_archetypes"]["content"]["npcs"][0]["implementation_notes"] = []
        else:
            broken["quest_hooks"]["content"]["quests"][0]["failure_states"] = ["Fail after three attempts."]
        with pytest.raises(ValueError):
            validate_design_approval(broken, evidence, critique, confirmations)


@pytest.mark.parametrize("section,records", [("npc_archetypes", "npcs"), ("quest_hooks", "quests")])
def test_empty_record_collections_are_visible_as_incomplete_sections(section, records):
    content = complete_artifact()
    content[section]["content"][records] = []
    scorecard = assess_artifact_quality(content)
    assert section in scorecard["incomplete_sections"]
    assert metric(scorecard, "completeness")["passed"] is False


@pytest.mark.parametrize("defer_runtime", [False, True])
def test_confirmation_survives_review_dispatch_and_is_audited_at_worker_boundary(monkeypatch, defer_runtime):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.config import settings
    from app.design_agent import workflow as workflow_module
    from app.design_agent.grounding import validate_generated_blueprint
    from app.design_agent.service import DesignAgentService
    from app.design_agent.jobs import DesignAgentJobService
    from app.models.design_agent import DesignAgentArtifact, DesignAgentCritique, DesignAgentEvidenceSnapshot

    content = complete_artifact()
    content["quest_hooks"]["content"]["quests"][0]["failure_states"] = ["Leave training early."]
    scope = {"defer_runtime": True} if defer_runtime else {}
    if defer_runtime:
        content["unity_runtime_preview"] = {"content": {}, "citations": [], "confidence": "Low",
                                             "warnings": ["Runtime explicitly deferred."]}
    npc = content["npc_archetypes"]["content"]["npcs"][0]
    npc["assumptions"] = ["Proposal: show the warning at mission entry; not runtime-tested."]
    evidence = [{"chunk_id": content["summary"]["citations"][0], "matched_sections": list(BLUEPRINT_SECTION_KEYS),
                 "content": "Mira mentors training. Check the route before moving. Learn core mechanics. "
                            "Unlock weak\u2011password gate. Leave training early. PATCH teaches core mechanics."}]
    content = validate_generated_blueprint(content, evidence)
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in assess_artifact_quality(content)["unresolved_assumptions"]]
    critique = {"verdict": "ready_for_review", "findings": [], "quality_scorecard": assess_artifact_quality(content, review_request=scope)}
    artifact_id, run_id, snapshot_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    artifact = SimpleNamespace(id=artifact_id, content=content, evidence_snapshot_id=snapshot_id,
                               immutable=False, artifact_type="draft", run_id=run_id, game_project_id="qa")
    run = SimpleNamespace(id=run_id, provider_name="nvidia", game_project_id="qa", status="awaiting_review",
                          revision_count=0, max_revisions=2, model_config=scope, objective="Review training design.")
    reviewer = SimpleNamespace(id=uuid.uuid4(), email="designer@example.test")
    rows = {DesignAgentArtifact: artifact, DesignAgentEvidenceSnapshot: SimpleNamespace(items=evidence),
            DesignAgentCritique: SimpleNamespace(content=critique, provider_name="mock")}
    db = MagicMock()
    def query(model):
        from sqlalchemy.sql import operators
        result = MagicMock()
        def filtered(*clauses):
            # Final snapshots and the latest editable draft are different queries.
            final_query = model is DesignAgentArtifact and any(
                getattr(getattr(clause, "left", None), "key", None) == "artifact_type"
                and getattr(getattr(clause, "right", None), "value", None) == "final"
                and clause.operator is operators.eq for clause in clauses)
            result.first.return_value = None if final_query else rows.get(model)
            return result
        result.filter.side_effect = filtered
        result.order_by.return_value = result
        result.first.return_value = rows.get(model)
        return result
    db.query.side_effect = query
    transport = MagicMock()
    service = DesignAgentService(transport)
    monkeypatch.setattr(service, "_get_run", lambda *_args: run)
    monkeypatch.setattr(service, "_response", lambda *_args: "review-response")
    monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
    assert service.review(db, run_id, "qa", "approve", None, reviewer,
                          artifact_id=artifact_id, confirmed_proposals=confirmations) == "review-response"
    decision = transport.resume.call_args.args[1]
    assert [item.model_dump() for item in decision.confirmed_proposals] == confirmations
    assert decision.artifact_id == artifact_id
    transport.resume.reset_mock()
    with pytest.raises(HTTPException) as stale:
        service.review(db, run_id, "qa", "approve", None, reviewer,
                       artifact_id=uuid.uuid4(), confirmed_proposals=confirmations)
    assert stale.value.status_code == 409
    transport.resume.assert_not_called()
    enqueue = MagicMock()
    monkeypatch.setattr(DesignAgentJobService, "enqueue_resume", enqueue)
    monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "queued")
    service.review(db, run_id, "qa", "approve", None, reviewer,
                   artifact_id=artifact_id, confirmed_proposals=confirmations)
    queued_decision = enqueue.call_args.args[2]
    assert queued_decision.model_dump(mode="json") == decision.model_dump(mode="json")

    workflow = workflow_module.DesignAgentWorkflow.__new__(workflow_module.DesignAgentWorkflow)
    monkeypatch.setattr(workflow, "_session", lambda: nullcontext(db))
    monkeypatch.setattr(workflow, "_load_run", lambda *_args: run)
    execution = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(workflow, "_begin_execution", lambda *_args, **_kwargs: execution)
    completed = MagicMock()
    monkeypatch.setattr(workflow, "_complete_execution", completed)
    monkeypatch.setattr(workflow_module, "interrupt", lambda _payload: queued_decision.model_dump(mode="json"))
    state = {"run_id": str(run_id), "game_project_id": "qa", "current_artifact_id": str(artifact_id),
             "current_artifact_version": 1, "current_artifact": content, "evidence_items": evidence, "critique": critique}
    db.add.reset_mock()
    update = workflow._human_review(state)
    assert update["confirmed_proposals"] == confirmations
    details = completed.call_args.kwargs["details"]
    assert details["artifact_id"] == str(artifact_id) and details["confirmed_proposals"] == confirmations
    assert details["reviewer_user_id"] == str(reviewer.id) and details["reviewer_label"] == reviewer.email
    assert db.add.call_args.args[0].artifact_id == artifact_id
    assert content["npc_archetypes"]["content"]["npcs"][0]["assumptions"]
    artifact.id = uuid.uuid4()  # A newer artifact appears while the job waits.
    db.add.reset_mock()
    completed.reset_mock()
    with pytest.raises(ValueError, match="queued approval is stale"):
        workflow._human_review(state)
    db.add.assert_not_called()
    completed.assert_not_called()

    # Finalization uses the same gate even if it is invoked without the review node.
    artifact.id = artifact_id
    rows[DesignAgentArtifact] = None
    workflow.provider = SimpleNamespace(name="nvidia")
    run.document_ids = [str(uuid.uuid4())]
    state["evidence_snapshot_id"] = str(snapshot_id)
    monkeypatch.setattr(workflow, "_fail_execution", MagicMock())
    db.add.reset_mock()
    with pytest.raises(ValueError, match="the approval is stale"):
        workflow._finalize(state)
    db.add.assert_not_called()
    state.update(update)
    rows[DesignAgentArtifact] = artifact
    def assign_ids():
        for call in db.add.call_args_list:
            if call.args[0].id is None:
                call.args[0].id = uuid.uuid4()
    db.flush.side_effect = assign_ids
    db.refresh.side_effect = lambda _record: assign_ids()
    result = workflow._finalize(state)
    blueprint, final_artifact = [call.args[0] for call in db.add.call_args_list]
    assert final_artifact.immutable and final_artifact.artifact_type == "final"
    assert final_artifact.content["npc_archetypes"]["content"]["npcs"][0]["assumptions"] == npc["assumptions"]
    assert blueprint.status == "approved" and not blueprint.materialization_manifest
    assert blueprint.unity_runtime_preview.get("runtime_deferred", False) is defer_runtime
    assert result["blueprint_id"] == str(blueprint.id)


def test_proposal_confirmation_persists_through_authenticated_api_and_worker(db_session, monkeypatch):
    """Real PostgreSQL checkpoints and review records; hosted output is a local fixture."""
    import httpx
    from fastapi.testclient import TestClient
    from app.api.v1.design_agent import get_design_agent_service
    from app.config import settings
    from app.design_agent.jobs import DesignAgentJobService
    from app.design_agent.provider import MockDesignAgentProvider, ProviderResult
    from app.design_agent.workflow import DesignAgentWorkflow
    from app.models.blueprint import GameBlueprint
    from app.models.design_agent import (
        DesignAgentArtifact, DesignAgentEvidenceSnapshot, DesignAgentJob,
        DesignAgentNodeExecution, DesignAgentReviewEvent, DesignAgentRun,
    )
    from app.models.project import GameProject
    from app.models.user import ProjectMembership, User
    from app.security import SESSION_COOKIE_NAME, create_access_token
    from main import app
    from test_design_agent_workflow import CountingRAG, create_source, make_service

    def forbid_http(*_args, **_kwargs):
        pytest.fail("External HTTP is forbidden in the proposal acceptance check")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbid_http)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbid_http)
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "DESIGN_AGENT_JOB_MAX_ATTEMPTS", 1)

    class FixtureProvider(MockDesignAgentProvider):
        name = "nvidia"

        def generate(self, plan, evidence):
            content = complete_artifact(evidence[0]["chunk_id"])
            content["npc_archetypes"]["content"]["npcs"][0]["assumptions"] = [
                "Proposal: show the warning at mission entry; not runtime-tested."
            ]
            quest = content["quest_hooks"]["content"]["quests"][0]
            quest["failure_states"] = ["Leave training before completing the mission."]
            quest["assumptions"] = ["Proposal: complete training on a gate-open event; not a GDD fact."]
            return ProviderResult(content=content, provider_name=self.name, model_name="local-acceptance-fixture")

        def critique(self, artifact, evidence, *, review_request=None):
            return ProviderResult(content={"verdict": "ready_for_review", "findings": [],
                                          "summary": "Fixture permits human review, not runtime approval."},
                                  provider_name=self.name, model_name="local-acceptance-fixture")

    reviewer = User(email=f"proposal-{uuid.uuid4().hex}@example.test", password_hash="unused-in-cookie-test",
                    email_verified=True, is_active=True, session_version=1)
    db_session.add(reviewer)
    db_session.commit()
    client = TestClient(app)  # No lifespan: do not backfill the normal vector store.
    token = create_access_token(str(reviewer.id), reviewer.session_version)
    try:
        for mode in ("inline", "queued", "queued_stale"):
            project = f"proposal_{mode}_{uuid.uuid4().hex[:8]}"
            db_session.add(GameProject(id=project, name="Isolated proposal QA"))
            db_session.flush()
            membership = ProjectMembership(user_id=reviewer.id, game_project_id=project, role="editor")
            db_session.add(membership)
            db_session.commit()
            document, chunks = create_source(db_session, project)
            chunks[0].content += (" Mira mentors training. Check the route before moving. Learn core mechanics. "
                                  "Unlock weak-password gate. Leave training before completing the mission. "
                                  "PATCH teaches core mechanics.")
            db_session.commit()
            rag = CountingRAG(chunks)
            service = make_service(db_session, rag, FixtureProvider())
            app.dependency_overrides[get_design_agent_service] = lambda: service
            monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
            client.cookies.set(SESSION_COOKIE_NAME, token)
            headers = {"X-Game-Project-ID": project}
            response = client.post("/api/v1/design-agent/runs", headers=headers, json={
                "objective": "Check explicit proposal confirmation and durable approval.",
                "document_ids": [str(document.id)], "hosted_provider_consent": True,
            })
            assert response.status_code == 201, response.text
            run = response.json()
            run_id = uuid.UUID(run["id"])
            artifact = run["current_artifact"]
            critique_before = copy.deepcopy(run["critique"]["content"])
            pending = critique_before["quality_scorecard"]["unresolved_assumptions"]
            assert len(pending) >= 2 and critique_before["quality_scorecard"]["blockers"] == ["Integration readiness"]
            confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")} for item in pending]
            payload = {"decision": "approve", "artifact_id": artifact["id"], "confirmed_proposals": confirmations}
            path = f"/api/v1/design-agent/runs/{run_id}/review"
            # Auth and workspace role enforcement must precede any review write.
            client.cookies.clear()
            assert client.post(path, headers=headers, json=payload).status_code == 401
            client.cookies.set(SESSION_COOKIE_NAME, token)
            assert client.post(path, headers={"X-Game-Project-ID": "another-project"}, json=payload).status_code == 403
            membership.role = "viewer"
            db_session.commit()
            assert client.post(path, headers=headers, json=payload).status_code == 403
            membership.role = "editor"
            db_session.commit()
            for invalid in (
                {**payload, "artifact_id": str(uuid.uuid4())},
                {**payload, "confirmed_proposals": []},
                {**payload, "confirmed_proposals": confirmations[:-1]},
                {**payload, "confirmed_proposals": [*confirmations, confirmations[0]]},
                {**payload, "confirmed_proposals": [{**confirmations[0], "assumption": "Different proposal"}, *confirmations[1:]]},
            ):
                rejected = client.post(path, headers=headers, json=invalid)
                assert rejected.status_code == 409, rejected.text
            assert client.post(path, headers=headers, json={"decision": "approve", "confirmed_proposals": confirmations}).status_code == 422
            assert db_session.query(DesignAgentReviewEvent).filter_by(run_id=run_id).count() == 0
            assert db_session.query(DesignAgentJob).filter_by(run_id=run_id).count() == 0
            assert db_session.query(GameBlueprint).filter_by(game_project_id=project).count() == 0
            db_session.expire_all()
            assert db_session.get(DesignAgentRun, run_id).status == "awaiting_review"
            draft = db_session.get(DesignAgentArtifact, uuid.UUID(artifact["id"]))
            # A later snapshot must not replace the draft's frozen evidence at approval.
            db_session.add(DesignAgentEvidenceSnapshot(run_id=run_id, game_project_id=project,
                           revision=2, query="Unrelated later retrieval", items=[]))
            db_session.commit()
            monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline" if mode == "inline" else "queued")
            approved = client.post(path, headers=headers, json=payload)
            assert approved.status_code == 200, approved.text
            if mode != "inline":
                assert approved.json()["status"] == "review_queued"
                job = db_session.query(DesignAgentJob).filter_by(run_id=run_id).one()
                assert job.payload["confirmed_proposals"] == confirmations and job.payload["artifact_id"] == artifact["id"]
                if mode == "queued_stale":
                    db_session.add(DesignAgentArtifact(run_id=run_id, game_project_id=project, version=2,
                                   artifact_type="revision", evidence_snapshot_id=draft.evidence_snapshot_id,
                                   content=copy.deepcopy(draft.content), immutable=False))
                    db_session.commit()
                # New workflow instance reloads the real PostgreSQL checkpoint after queuing.
                worker = DesignAgentJobService(service.workflow.session_factory, workflow_factory=lambda factory:
                    DesignAgentWorkflow(database_url=settings.DATABASE_URL, session_factory=factory,
                                        provider=FixtureProvider(), rag_service=rag))
                assert worker.process_one("isolated-proposal-qa")
                db_session.expire_all()
                db_session.refresh(job)
                if mode == "queued_stale":
                    assert job.status == "failed" and "queued approval is stale" in job.last_error
                    assert db_session.query(DesignAgentReviewEvent).filter_by(run_id=run_id).count() == 0
                    assert db_session.query(GameBlueprint).filter_by(game_project_id=project).count() == 0
                    continue
                assert job.status == "succeeded", job.last_error
            db_session.expire_all()
            assert db_session.get(DesignAgentRun, run_id).status == "completed"
            review = db_session.query(DesignAgentReviewEvent).filter_by(run_id=run_id).one()
            assert review.artifact_id == draft.id and review.reviewer_user_id == reviewer.id
            assert review.reviewer_label == reviewer.email and review.created_at is not None
            execution = db_session.query(DesignAgentNodeExecution).filter_by(run_id=run_id, node_name="human_review", status="completed").one()
            assert execution.details["confirmed_proposals"] == confirmations
            assert execution.details["artifact_id"] == artifact["id"] and execution.details["artifact_version"] == artifact["version"]
            final = db_session.query(DesignAgentArtifact).filter_by(run_id=run_id, artifact_type="final").one()
            assert final.immutable and final.evidence_snapshot_id == draft.evidence_snapshot_id
            assert final.content == draft.content  # Proposal labels remain in the final design.
            blueprint = db_session.get(GameBlueprint, final.blueprint_id)
            assert blueprint.status == "approved" and not blueprint.materialization_manifest
            stored = client.get(f"/api/v1/design-agent/runs/{run_id}", headers=headers).json()
            assert stored["critique"]["content"] == critique_before  # Historical metrics are not rewritten.
            assert client.post(path, headers=headers, json=payload).status_code == 409
            assert db_session.query(DesignAgentReviewEvent).filter_by(run_id=run_id).count() == 1
            assert rag.calls == 1
    finally:
        client.close()
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_partial_revision_does_not_persist_an_artifact_or_recritique(db_session):
    from app.api.v1.design_agent import get_design_agent_service
    from app.design_agent.provider import MockDesignAgentProvider, ProviderResult
    from app.models.design_agent import DesignAgentArtifact, DesignAgentCritique, DesignAgentRun
    from app.models.blueprint import GameBlueprint
    from main import app
    from test_design_agent_workflow import CountingRAG, client, create_source, make_service, start_run

    class PartialRevisionProvider(MockDesignAgentProvider):
        def generate(self, plan, evidence):
            return ProviderResult(content=complete_artifact(evidence[0]["chunk_id"]),
                                  provider_name=self.name, model_name=self.model_name)

        def revise(self, artifact, evidence, rejection_reason, target_sections=None, *, review_request=None):
            revised = copy.deepcopy(artifact)
            revised["npc_archetypes"]["content"]["npcs"][0]["dialogue_hooks"] = ["Inspect the link before clicking."]
            return ProviderResult(content=revised, provider_name=self.name, model_name=self.model_name)

    project = f"partial_revision_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project)
    rag = CountingRAG(chunks)
    service = make_service(db_session, rag, PartialRevisionProvider())
    try:
        run = start_run(service, document.id, project)
        response = client.post(f"/api/v1/design-agent/runs/{run['id']}/review",
                               headers={"X-Game-Project-ID": project},
                               json={"decision": "reject", "reason": "Correct dialogue and quests.",
                                     "target_sections": ["npc_archetypes", "quest_hooks"]})
        assert response.status_code == 502, response.text
        run_id = uuid.UUID(run["id"])
        db_session.expire_all()
        stored_run = db_session.get(DesignAgentRun, run_id)
        assert stored_run.status == "awaiting_review" and stored_run.revision_count == 0
        assert stored_run.model_config['consecutive_revision_failures'] == 1
        assert "quest_hooks" in stored_run.last_error
        assert db_session.query(DesignAgentArtifact).filter_by(run_id=run_id).count() == 1
        assert db_session.query(DesignAgentCritique).filter_by(run_id=run_id).count() == 1
        assert db_session.query(GameBlueprint).filter_by(game_project_id=project).count() == 0
        assert rag.calls == 1
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_approval_rechecks_completeness_instead_of_trusting_legacy_scorecard(db_session):
    from app.api.v1.design_agent import get_design_agent_service
    from app.design_agent.provider import MockDesignAgentProvider, ProviderResult
    from app.models.design_agent import DesignAgentArtifact, DesignAgentCritique, DesignAgentReviewEvent
    from main import app
    from test_design_agent_workflow import CountingRAG, client, create_source, make_service, start_run

    project = f"legacy_score_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project)
    class FakeHostedProvider(MockDesignAgentProvider):
        name = "nvidia"

        def generate(self, plan, evidence):
            content = complete_artifact(evidence[0]["chunk_id"])
            content["quest_hooks"]["content"]["quests"][0]["failure_states"] = ["Leave training before completing the mission."]
            return ProviderResult(content=content, provider_name=self.name, model_name=self.model_name)

    service = make_service(db_session, CountingRAG(chunks), FakeHostedProvider())
    try:
        run = start_run(service, document.id, project)
        run_id = uuid.UUID(run["id"])
        artifact = db_session.query(DesignAgentArtifact).filter_by(run_id=run_id).one()
        original = copy.deepcopy(artifact.content)
        critique = db_session.query(DesignAgentCritique).filter_by(run_id=run_id).one()
        critique.content = {"verdict": "ready_for_review", "findings": [], "summary": "Legacy pass",
                            "quality_scorecard": {"passed": True, "blockers": []}}
        for fault, blocker in (("empty", "Completeness"), ("quest_checks", "Integration readiness")):
            content = copy.deepcopy(original)
            if fault == "empty":
                content["gameplay_systems"]["content"] = {}
            else:
                content["quest_hooks"]["content"]["quests"][0]["implementation_notes"] = ["Map objectives to game events."]
            artifact.content = content
            db_session.commit()
            confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                             for item in assess_artifact_quality(content)["unresolved_assumptions"]]
            response = client.post(f"/api/v1/design-agent/runs/{run['id']}/review",
                                   headers={"X-Game-Project-ID": project},
                                   json={"decision": "approve", "artifact_id": str(artifact.id),
                                         "confirmed_proposals": confirmations})
            assert response.status_code == 409, response.text
            assert blocker in response.json()["detail"]
            assert db_session.query(DesignAgentReviewEvent).filter_by(run_id=run_id).count() == 0
            db_session.refresh(critique)
            assert critique.content["summary"] == "Legacy pass"  # Do not rewrite historical critiques.
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
