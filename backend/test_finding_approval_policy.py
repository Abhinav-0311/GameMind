"""Human finding resolutions affect only a later explicit approval; isolated SQLite."""
import copy
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.design_agent.grounding import assess_artifact_quality, complete_design_critique, validate_generated_blueprint
from app.models import design_agent as models
from test_design_finding_resolutions import audit_client, post, submission
from test_revision_completeness_guards import complete_artifact


def test_quality_review_requirement_preserves_legacy_and_explicit_scope():
    from app.design_agent.review_policy import requires_design_quality_review

    for provider, config, proposals, expected in [
        ("mock", None, None, False),
        ("mock", {}, [], False),
        ("mock", {"fresh_dialogue": False, "defer_runtime": False}, [], False),
        ("nvidia", None, [], True),
        ("mock", {"fresh_dialogue": True}, [], True),
        ("mock", {"fresh_dialogue": "legacy-truthy"}, [], True),
        ("mock", {"defer_runtime": True}, [], True),
        ("mock", {"defer_runtime": "true"}, [], False),
        ("mock", {"defer_runtime": 1}, [], False),
        ("mock", {}, [{"assumption": "Designer proposal"}], True),
    ]:
        run = SimpleNamespace(provider_name=provider, model_config=config)
        original = copy.deepcopy((run, proposals))
        assert requires_design_quality_review(run, proposals) is expected
        assert (run, proposals) == original


def prepared(audit_client, *, provenance=True, extra_finding=False):
    from app.design_agent.review_policy import build_review_provenance, saved_review_request

    client, _, db, url, _, ids, _ = audit_client
    run = db.get(models.DesignAgentRun, ids[0])
    run.provider_name = "nvidia"
    artifact = db.get(models.DesignAgentArtifact, ids[1])
    snapshot = db.get(models.DesignAgentEvidenceSnapshot, ids[2])
    critique = db.get(models.DesignAgentCritique, ids[3])
    content = complete_artifact("frozen-1")
    content["npc_archetypes"]["content"]["npcs"][0]["dialogue_style"] = "formal, slow"
    evidence = copy.deepcopy(snapshot.items)
    evidence[0]["content"] += " Unlock the weak-password gate. Fail to complete mission within time limit."
    evidence[0]["matched_sections"] = list(content)
    artifact.content = validate_generated_blueprint(content, evidence)
    snapshot.items = evidence
    raw = copy.deepcopy(critique.content)
    if extra_finding:
        raw["findings"].append({**raw["findings"][0], "issue": "Another independent concern."})
    request = saved_review_request(run)
    critique.content = complete_design_critique(raw, artifact.content, evidence=evidence, review_request=request)
    if provenance:
        critique.content = {**critique.content, "model_review_provenance":
                            build_review_provenance(raw, artifact.content, evidence, request, clean=True)}
    db.commit()
    proposals = [{key: item[key] for key in ("section", "record_id", "assumption")}
                 for item in assess_artifact_quality(artifact.content)["unresolved_assumptions"]]
    return client, db, url, run, artifact, snapshot, critique, proposals


def approve(db, run, artifact, proposals):
    from app.design_agent.review_policy import validate_persisted_design_approval
    return validate_persisted_design_approval(db, run, artifact, proposals)


def referenced(audit_client, *, object_field=False, stale_value=False):
    from app.design_agent.finding_reviews import _artifact_value
    from app.design_agent.review_policy import build_review_provenance, saved_review_request
    result = prepared(audit_client)
    _, db, _, run, artifact, snapshot, critique, _ = result
    path = "/npc_archetypes/content/npcs/0" + ("" if object_field else "/dialogue_style")
    raw = copy.deepcopy(critique.content["model_review_provenance"]["model_output"])
    raw["review_mode"] = "defect_detection"
    raw["findings"][0]["reference"] = {
        "artifact_path": path, "artifact_value": "stale" if stale_value else _artifact_value(artifact.content, path),
        "evidence_chunk_id": "frozen-1", "evidence_quote": "Mira speaks in a formal and slow manner."}
    request = saved_review_request(run)
    critique.content = {**complete_design_critique(raw, artifact.content, evidence=snapshot.items, review_request=request),
        "model_review_provenance": build_review_provenance(raw, artifact.content, snapshot.items, request, clean=True)}
    db.commit()
    return result, path


@pytest.mark.parametrize("case", ["scalar", "object", "other-field", "stale-reference"])
def test_record_reference_binding(audit_client, case):
    from app.design_agent.finding_reviews import _artifact_value
    result, path = referenced(audit_client, object_field=case == "object", stale_value=case == "stale-reference")
    client, db, url, run, artifact, _, critique, proposals = result
    original = copy.deepcopy(critique.content)
    payload = submission(client, url) | {"artifact_path": "/npc_archetypes/content/npcs/0/name" if case == "other-field" else path}
    response = post(client, url, payload)
    if case in {"other-field", "stale-reference"}:
        assert response.status_code == 422, response.text
        assert db.query(models.DesignAgentFindingResolution).count() == 0
    else:
        assert response.status_code == 201, response.text
        assert response.json()["artifact_value"] == _artifact_value(artifact.content, path)
        assert approve(db, run, artifact, proposals)["passed"]
    assert critique.content == original and run.status == "awaiting_review" and not artifact.immutable


def test_replayed_reference_binding_rejects_old_mismatched_record_without_rewriting_it(audit_client):
    result, path = referenced(audit_client)
    client, db, url, run, artifact, _, critique, proposals = result
    assert post(client, url, submission(client, url) | {"artifact_path": path}).status_code == 201
    record = db.query(models.DesignAgentFindingResolution).one()
    record.artifact_path = "/npc_archetypes/content/npcs/0/name"
    record.artifact_value = "Mira"
    db.commit()
    original = copy.deepcopy((record.finding_content, critique.content, record.id))
    with pytest.raises(ValueError, match="Independent critique"):
        approve(db, run, artifact, proposals)
    catalog = client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()
    assert not catalog["findings"][0]["resolution_applies"] and catalog["critique_blocked"]
    assert not catalog["findings"][0]["can_resolve"]  # Existing audit cannot be overwritten.
    assert (record.finding_content, critique.content, record.id) == original


def test_recorded_model_finding_can_be_resolved_without_rewriting_raw_review(audit_client):
    client, db, url, run, artifact, _, critique, proposals = prepared(audit_client)
    original = copy.deepcopy(critique.content)
    with pytest.raises(ValueError, match="Independent critique"):
        approve(db, run, artifact, proposals)
    assert post(client, url, submission(client, url)).status_code == 201
    assert approve(db, run, artifact, proposals)["passed"]
    assert critique.content == original and run.status == "awaiting_review"
    assert artifact.immutable is False and artifact.blueprint_id is None


@pytest.mark.parametrize("change", ["legacy", "artifact", "evidence", "critique", "request", "dirty", "actor", "scope", "value", "quote"])
def test_unknown_stale_or_invalid_resolution_cannot_unlock_approval(audit_client, change):
    client, db, url, run, artifact, snapshot, critique, proposals = prepared(audit_client, provenance=change != "legacy")
    if change == "dirty":
        critique.content = {**critique.content, "model_review_provenance":
                            {**critique.content["model_review_provenance"], "clean": False}}
        db.commit()
    assert post(client, url, submission(client, url)).status_code == 201
    record = db.query(models.DesignAgentFindingResolution).one()
    if change == "artifact":
        artifact.content = {**artifact.content, "summary": {**artifact.content["summary"], "warnings": ["Changed"]}}
    elif change == "evidence":
        snapshot.items = [{**snapshot.items[0], "content": "Different frozen source."}]
    elif change == "critique":
        critique.content = {**critique.content, "summary": "Changed review."}
    elif change == "request":
        run.objective += " Also add dialogue."
    elif change == "actor":
        record.reviewer_user_id = None
    elif change == "scope":
        record.artifact_version += 1
    elif change == "value":
        record.artifact_value = "An unrelated voice"
    elif change == "quote":
        record.evidence_quote = "Invented supporting evidence"
    db.commit()
    with pytest.raises(ValueError, match="Independent critique"):
        approve(db, run, artifact, proposals)


def test_resolution_never_confirms_design_proposals(audit_client):
    client, db, url, run, artifact, _, _, proposals = prepared(audit_client)
    assert proposals
    assert post(client, url, submission(client, url)).status_code == 201
    with pytest.raises(ValueError, match="Integration readiness"):
        approve(db, run, artifact, [])


def test_partial_model_resolution_still_blocks(audit_client):
    client, db, url, run, artifact, _, _, proposals = prepared(audit_client, extra_finding=True)
    assert post(client, url, submission(client, url)).status_code == 201
    with pytest.raises(ValueError, match="Independent critique"):
        approve(db, run, artifact, proposals)


def test_server_blocker_cannot_be_dismissed_even_with_a_record(audit_client):
    from app.design_agent.review_policy import build_review_provenance, saved_review_request
    client, db, url, run, artifact, snapshot, critique, proposals = prepared(audit_client)
    content = copy.deepcopy(artifact.content)
    content["summary"]["content"] = {}
    artifact.content = content
    raw = {"verdict": "ready_for_review", "summary": "Looks good.", "findings": []}
    request = saved_review_request(run)
    critique.content = {**complete_design_critique(raw, content, evidence=snapshot.items, review_request=request),
                        "model_review_provenance": build_review_provenance(raw, content, snapshot.items, request, clean=True)}
    db.commit()
    payload = submission(client, url)
    assert post(client, url, payload).status_code == 201
    with pytest.raises(ValueError, match="Independent critique"):
        approve(db, run, artifact, proposals)


def test_unexplained_negative_verdict_is_not_overridden(audit_client):
    from app.design_agent.review_policy import build_review_provenance, saved_review_request
    _, db, _, run, artifact, snapshot, critique, proposals = prepared(audit_client)
    raw = {"verdict": "needs_revision", "summary": "Unexplained concern.", "findings": []}
    request = saved_review_request(run)
    critique.content = {**complete_design_critique(raw, artifact.content, evidence=snapshot.items, review_request=request),
                        "model_review_provenance": build_review_provenance(raw, artifact.content, snapshot.items, request, clean=True)}
    db.commit()
    with pytest.raises(ValueError, match="Independent critique"):
        approve(db, run, artifact, proposals)


@pytest.mark.parametrize("field", ["content", "evidence", "critique"])
def test_worker_checkpoint_must_match_persisted_review(audit_client, field):
    from app.design_agent.review_policy import validate_persisted_design_approval
    client, db, url, run, artifact, snapshot, critique, proposals = prepared(audit_client)
    assert post(client, url, submission(client, url)).status_code == 201
    expected = {"content": artifact.content, "evidence": snapshot.items, "critique": critique.content}
    expected[field] = {} if field != "evidence" else []
    with pytest.raises(ValueError, match="stale"):
        validate_persisted_design_approval(db, run, artifact, proposals, expected=expected)


@pytest.mark.parametrize("mode", ["inline", "queued"])
def test_api_uses_resolutions_only_for_explicit_approval(audit_client, monkeypatch, mode):
    from app.config import settings
    from app.design_agent.jobs import DesignAgentJobService
    from app.design_agent.service import DesignAgentService
    from app.models.user import User
    from fastapi import HTTPException

    client, db, url, run, artifact, _, _, proposals = prepared(audit_client)
    transport = MagicMock()
    service = DesignAgentService(transport)
    service._response = lambda _db, row: row
    enqueue = MagicMock()
    monkeypatch.setattr(DesignAgentJobService, "enqueue_resume", enqueue)
    monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", mode)
    with pytest.raises(HTTPException) as blocked:
        service.review(db, run.id, run.game_project_id, "approve", None, db.query(User).one(),
                       artifact_id=artifact.id, confirmed_proposals=proposals)
    assert blocked.value.status_code == 409
    enqueue.assert_not_called()
    transport.resume.assert_not_called()
    assert post(client, url, submission(client, url)).status_code == 201
    enqueue.assert_not_called()  # Recording alone must not resume any workflow.
    service.review(db, run.id, run.game_project_id, "approve", None, db.query(User).one(),
                   artifact_id=artifact.id, confirmed_proposals=proposals)
    (enqueue if mode == "queued" else transport.resume).assert_called_once()
    assert run.status == "awaiting_review" and artifact.blueprint_id is None


@pytest.mark.parametrize("boundary", ["worker_review", "finalize"])
def test_worker_and_finalization_recheck_resolution_records(audit_client, monkeypatch, boundary):
    from app.design_agent import workflow as module
    from app.design_agent.review_policy import validate_persisted_design_approval

    client, db, url, run, artifact, snapshot, critique, proposals = prepared(audit_client)
    proxy = MagicMock(wraps=db)
    def query(model):
        if model is models.DesignAgentNodeExecution:
            result = MagicMock()
            result.filter.return_value = result.order_by.return_value = result
            result.first.return_value = None
            return result
        return db.query(model)
    proxy.query.side_effect = query
    proxy.get.side_effect = lambda model, identity: (SimpleNamespace(id=identity)
        if model is models.DesignAgentNodeExecution else db.get(model, identity))
    workflow = object.__new__(module.DesignAgentWorkflow)
    workflow._session = lambda: nullcontext(proxy)
    workflow._load_run = lambda *_args: run
    workflow._begin_execution = lambda *_args, **_kwargs: SimpleNamespace(id=uuid4())
    workflow._fail_execution = MagicMock()
    state = {"run_id": str(run.id), "current_artifact_id": str(artifact.id), "current_artifact_version": 1,
             "current_artifact": artifact.content, "evidence_items": snapshot.items, "critique": critique.content,
             "confirmed_proposals": proposals}
    monkeypatch.setattr(module, "interrupt", lambda _: {"decision": "approve", "artifact_id": str(artifact.id),
                                                         "confirmed_proposals": proposals})
    method = workflow._human_review if boundary == "worker_review" else workflow._finalize
    with pytest.raises(ValueError, match="Independent critique"):
        method(state)
    assert post(client, url, submission(client, url)).status_code == 201
    class GatePassed(Exception):
        pass
    def stop_after_gate(*args, **kwargs):
        assert validate_persisted_design_approval(*args, **kwargs)["passed"]
        raise GatePassed()  # Exercise the real gate, stop before review/runtime writes.
    monkeypatch.setattr(module, "validate_persisted_design_approval", stop_after_gate)
    with pytest.raises(GatePassed):
        method(state)
    proxy.add.assert_not_called()
    assert artifact.blueprint_id is None and critique.content["verdict"] == "needs_revision"


@pytest.mark.parametrize("recovered", [False, True])
def test_adapter_origin_is_server_generated_not_model_supplied(audit_client, monkeypatch, recovered):
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from app.design_agent.provider import ProviderResult
    from app.design_agent.review_policy import build_review_provenance, saved_review_request

    _, _, _, run, artifact, snapshot, critique, _ = prepared(audit_client)
    raw = copy.deepcopy(critique.content["model_review_provenance"]["model_output"])
    raw["model_review_provenance"] = {"version": 999, "clean": True}
    provider = NvidiaDesignAgentProvider(llm_provider=MagicMock())
    monkeypatch.setattr(provider, "_invoke", lambda **_: ProviderResult(
        content=raw, model_name="offline-critic", provider_name="nvidia",
        metadata={"recovery_requires_review": recovered, "finding_review_provenance": {"forged": True}}))
    result = provider.critique(artifact.content, snapshot.items, review_request=saved_review_request(run))
    origin = result.metadata["finding_review_provenance"]
    assert origin == build_review_provenance(raw, artifact.content, snapshot.items, saved_review_request(run), clean=not recovered)
    assert "model_review_provenance" not in origin["model_output"]
    assert "model_review_provenance" not in result.content  # Only workflow persistence attaches it.


@pytest.mark.parametrize("provider_name", ["nvidia", "mock"])
def test_workflow_persists_origin_only_from_hosted_adapter_metadata(audit_client, provider_name):
    from app.design_agent.provider import ProviderResult
    from app.design_agent.workflow import DesignAgentWorkflow

    _, _, _, run, artifact, snapshot, critique, _ = prepared(audit_client)
    original = copy.deepcopy(critique.content)
    content = {key: value for key, value in original.items() if key != "model_review_provenance"}
    content["model_review_provenance"] = {"forged_in_model_content": True}
    result = ProviderResult(content=content, provider_name=provider_name, model_name="offline-test",
                            metadata={"finding_review_provenance": original["model_review_provenance"]})
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.refresh.side_effect = lambda row: setattr(row, "id", uuid4())
    workflow = object.__new__(DesignAgentWorkflow)
    workflow.provider = MagicMock(name=provider_name)
    workflow._provider_node = lambda state, name, call, persist: persist(db, run, result)
    state = {"current_artifact_id": str(artifact.id), "current_artifact": artifact.content,
             "evidence_items": snapshot.items}
    update = workflow._critique(state)
    if provider_name == "nvidia":
        assert update["critique"] == original
    else:
        assert "model_review_provenance" not in update["critique"]
    db.add.assert_called_once()


def test_model_duplicate_of_server_defect_cannot_be_resolved_away(audit_client):
    from app.design_agent.review_policy import build_review_provenance, saved_review_request
    client, db, url, run, artifact, snapshot, critique, proposals = prepared(audit_client)
    content = copy.deepcopy(artifact.content)
    content["summary"]["content"] = {}
    artifact.content = content
    request = saved_review_request(run)
    server = complete_design_critique({"verdict": "ready_for_review", "summary": "Review", "findings": []},
                                      content, evidence=snapshot.items, review_request=request)
    raw = {"verdict": "needs_revision", "summary": "Empty summary.", "findings": server["findings"]}
    critique.content = {**complete_design_critique(raw, content, evidence=snapshot.items, review_request=request),
                        "model_review_provenance": build_review_provenance(raw, content, snapshot.items, request, clean=True)}
    db.commit()
    assert post(client, url, submission(client, url)).status_code == 201
    with pytest.raises(ValueError, match="Independent critique"):
        approve(db, run, artifact, proposals)


def test_catalog_exposes_server_policy_and_keeps_raw_finding(audit_client):
    client, db, url, run, artifact, _, critique, proposals = prepared(audit_client)
    before = client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()
    assert before["can_record"] is True
    assert before["critique_blocked"] is True
    assert before["findings"][0]["origin"] == "model"
    assert before["findings"][0]["can_resolve"] is True
    assert post(client, url, submission(client, url)).status_code == 201
    after = client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()
    assert after["critique_blocked"] is False
    assert after["findings"][0]["resolution_applies"] is True
    assert after["findings"][0]["finding"] == critique.content["findings"][0]
    assert approve(db, run, artifact, proposals)["passed"]
    with pytest.raises(ValueError, match="Integration readiness"):
        approve(db, run, artifact, [])

    # A later system check must be visible without replacing the saved critique.
    original = copy.deepcopy(critique.content)
    artifact.content = {**artifact.content, "summary": {**artifact.content["summary"], "content": {}}}
    db.commit()
    current = client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()
    assert current["system_checks"]["quality_scorecard"]["incomplete_sections"] == ["summary"]
    assert any(item["section"] == "summary" for item in current["system_checks"]["findings"])
    assert current["critique_blocked"] is True
    assert critique.content == original
    assert current["findings"][0]["finding"] == original["findings"][0]


@pytest.mark.parametrize("case", ["legacy", "viewer", "anonymous", "server"])
def test_catalog_never_offers_an_ineligible_write(audit_client, case):
    from app.dependencies import get_current_user
    from app.models.user import ProjectMembership
    from app.design_agent.review_policy import build_review_provenance, saved_review_request
    client, db, url, run, artifact, snapshot, critique, _ = prepared(audit_client, provenance=case != "legacy")
    if case == "viewer":
        db.query(ProjectMembership).one().role = "viewer"
    elif case == "anonymous":
        audit_client[1].dependency_overrides[get_current_user] = lambda: None
    elif case == "server":
        content = copy.deepcopy(artifact.content)
        content["summary"]["content"] = {}
        artifact.content = content
        raw = {"verdict": "ready_for_review", "summary": "Review", "findings": []}
        request = saved_review_request(run)
        critique.content = {**complete_design_critique(raw, content, evidence=snapshot.items, review_request=request),
                            "model_review_provenance": build_review_provenance(raw, content, snapshot.items, request, clean=True)}
    db.commit()
    catalog = client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()
    if case in {"viewer", "anonymous"}:
        assert catalog["can_record"] is False
    else:
        assert catalog["findings"][0]["can_resolve"] is False
        assert catalog["findings"][0]["origin"] == ("server" if case == "server" else "unknown")
    assert catalog["critique_blocked"] is True


def test_unapplied_audit_migration_returns_safe_unavailable_response(audit_client, monkeypatch):
    from sqlalchemy.exc import ProgrammingError
    client, db, url, *_ = prepared(audit_client)
    original_query = db.query
    def query(model):
        if model is models.DesignAgentFindingResolution:
            result = MagicMock()
            result.filter_by.return_value = result.order_by.return_value = result
            result.all.side_effect = ProgrammingError("private SQL", {}, SimpleNamespace(pgcode="42P01"))
            return result
        return original_query(model)
    monkeypatch.setattr(db, "query", query)
    response = client.get(url, headers={"X-Game-Project-ID": "audit-a"})
    assert response.status_code == 503
    assert "prepared database migration" in response.json()["detail"]
    assert "private SQL" not in response.text
