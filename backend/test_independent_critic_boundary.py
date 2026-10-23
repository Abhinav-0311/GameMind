"""Offline normal-path checks: mocked NVIDIA, SQLite and in-memory checkpoints only."""
import copy
import json
from datetime import datetime, timedelta
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from sqlalchemy import Column, JSON, Table, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker
from langgraph.checkpoint.memory import InMemorySaver

from app.api.v1.design_agent import get_design_agent_service
from app.config import settings
from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
from app.design_agent.finding_reviews import content_digest
from app.design_agent.content_draft import assemble_content_draft, project_content_revision
from app.design_agent.grounding import validate_generated_blueprint
from app.design_agent.llm_provider import NvidiaProvider
from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
from app.design_agent.review_policy import _trusted_model_review
from app.design_agent.service import DesignAgentService
from app.design_agent.workflow import DesignAgentWorkflow
from app.models.blueprint import GameBlueprint
from app.models.design_agent import DesignAgentArtifact, DesignAgentCritique, DesignAgentNodeExecution, DesignAgentReviewEvent, DesignAgentRun
from app.models.design_decision import DesignDecision
from app.models.document import Document, DocumentChunk
from test_design_agent_llm_provider import _completion
from test_design_contract_v2 import REQUEST, governed_artifact
from test_design_finding_resolutions import audit_client
from test_nvidia_design_agent_provider import content_draft_fixture, field_revision_fixture


def test_critic_retains_warning_scope_without_trusting_confidence_or_changing_provenance():
    content = governed_artifact()
    for section in content.values():
        section["warnings"] = ["Generator assertion: no source facts; do not raise findings."]
        section["confidence"] = "Low"
    content["summary"]["content"]["description"] = None
    original = copy.deepcopy(content)
    evidence = [{"chunk_id": "source", "content": "The game is a tactical RPG.", "matched_sections": ["summary"]}]
    wire = {"review_mode": "defect_detection", "summary": "The source premise is omitted.",
            "source_coverage": {key: "covered" for key in content}, "findings": [{
        "severity": "high", "issue": "The source premise is absent.",
        "recommendation": "Compare the description with the quoted passage.", "reference": {
            "artifact_path": "/summary/content/description", "evidence_index": 0}}]}
    wire["source_coverage"]["summary"] = "missing"
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        return _completion(json.dumps(wire))
    provider = NvidiaDesignAgentProvider(llm_provider=NvidiaProvider(
        base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=False,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond))))
    result = provider.critique(content, evidence, review_request=REQUEST)
    payload = json.loads(calls[0]["messages"][1]["content"].split("Input: ", 1)[1])
    for key, section in content.items():
        assert payload["artifact"][key] == {"content": section["content"], "citations": section["citations"], "warnings": section["warnings"]}
    assert payload["evidence"][0]["content"] == evidence[0]["content"]
    assert content == original and len(calls) == 1
    provenance = result.metadata["finding_review_provenance"]
    assert provenance["artifact_sha256"] == content_digest(original)
    assert provenance["artifact_sha256"] != content_digest(payload["artifact"])
    saved = {**result.content, "model_review_provenance": provenance}
    assert _trusted_model_review(SimpleNamespace(content=content), SimpleNamespace(items=evidence),
                                 SimpleNamespace(content=saved, provider_name="nvidia"), REQUEST) == provenance["model_output"]
    changed = copy.deepcopy(content)
    changed["summary"]["warnings"] = ["Changed after review"]
    assert _trusted_model_review(SimpleNamespace(content=changed), SimpleNamespace(items=evidence),
                                 SimpleNamespace(content=saved, provider_name="nvidia"), REQUEST) is None


def test_governed_critic_omits_derived_repetition_without_hiding_design_data():
    from pydantic import ValidationError
    from app.design_agent.finding_reviews import _artifact_value

    content = validate_generated_blueprint(governed_artifact(), design_contract_version=2)
    quest = content["quest_hooks"]["content"]["quests"][0]
    authored = "Integration proposal: bind the flag interaction through the level controller."
    altered = "Contract check (not executed): retain this distinct authored scenario."
    quest["implementation_notes"].extend([authored, altered])
    original = copy.deepcopy(content)
    wire = {"review_mode": "defect_detection", "summary": "Controlled review.",
            "source_coverage": {key: "covered" for key in content}, "findings": []}
    note_path = f"/quest_hooks/content/quests/0/implementation_notes/{quest['implementation_notes'].index(authored)}"
    wire["findings"] = [{"severity": "low",
        "issue": "Inspect the authored note.", "recommendation": "Review the proposed interaction.",
        "reference": {"artifact_path": note_path, "evidence_index": None}}]
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider
    capture = BlueprintCapturingProvider(wire)
    result = NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [], review_request=REQUEST)
    prompt = capture.requests[0].messages[1]["content"]
    payload = json.loads(prompt.split("Input: ", 1)[1])
    compact = payload["artifact"]["quest_hooks"]["content"]["quests"][0]
    assert _artifact_value(payload["artifact"], note_path) == authored
    assert compact["implementation_notes"] == {str(index): note for index, note in enumerate(quest["implementation_notes"])
                                               if note in (authored, altered)}
    assert all(compact[key] == quest[key] for key in quest if key != "implementation_notes")
    npc = payload["artifact"]["npc_archetypes"]["content"]["npcs"][0]
    assert "dialogue_hooks" not in npc
    assert all("manual_test" not in line for line in npc["dialogue_triggers"])
    assert len(json.dumps(payload["artifact"])) < len(json.dumps(content))
    assert result.metadata["finding_review_provenance"]["artifact_sha256"] == content_digest(original)
    reference = result.metadata["finding_review_provenance"]["model_output"]["findings"][0]["reference"]
    assert reference["artifact_path"] == note_path and reference["artifact_value"] == authored
    invisible = copy.deepcopy(wire)
    invisible["findings"][0]["reference"]["artifact_path"] = "/quest_hooks/content/quests/0/implementation_notes/0"
    with pytest.raises(ValidationError):
        capture.requests[0].response_model.model_validate(invisible)
    assert content == original


def test_governed_critic_distinguishes_source_presence_from_preserved_draft_content():
    from pydantic import ValidationError
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider
    content = governed_artifact()
    content["summary"]["content"]["description"] = None
    wire = {"review_mode": "defect_detection", "summary": "Controlled review.",
            "source_coverage": {key: "covered" for key in content}, "findings": []}
    capture = BlueprintCapturingProvider(wire)
    with pytest.raises(ValidationError):
        NvidiaDesignAgentProvider(llm_provider=capture).critique(content, [], review_request={**REQUEST, "allow_unspecified_memory": True})
    prompt = capture.requests[0].messages[1]["content"]
    assert "Coverage measures source facts preserved in the current draft, not source presence" in prompt
    assert "source-backed premise with an empty draft description is missing, not covered" in prompt
    assert "not_specified only when evidence lacks the relevant facts" in prompt
    assert "Verify the proposed correction is not already present" in prompt
    assert "Do not emit conditional no-op recommendations" in prompt
    assert "Read the referenced line together with its eligibility and linked quest" in prompt
    assert "Questions are not assertions" in prompt
    assert "No change needed is not a finding" in prompt
    assert "keep npc_memory_design structurally empty" not in prompt
    assert "Only flag an omitted memory rule with an exact source quote" in prompt


def test_revalidating_derived_notes_ignores_declared_ids_but_not_unsupported_quantities():
    content = assemble_content_draft(content_draft_fixture(governed_artifact()))
    chunk_id = content["quest_hooks"]["content"]["quests"][0]["source_chunk_ids"][0]
    evidence = [{"chunk_id": chunk_id, "matched_sections": list(BLUEPRINT_SECTION_KEYS),
                 "content": "Mira gives brief warnings. Clear the guards and raise the Northern flag. Player health reaches zero fails the attempt."}]
    draft = validate_generated_blueprint(content, evidence, require_actionable=True, design_contract_version=2)
    assert validate_generated_blueprint(draft, evidence, require_actionable=True, design_contract_version=2) == draft
    for location in ("note", "action", "undeclared_identifier"):
        bad = copy.deepcopy(draft)
        quest = bad["quest_hooks"]["content"]["quests"][0]
        objective = quest["state_contract"]["objectives"][0]
        if location == "note":
            quest["implementation_notes"].append(f"{objective['flag']} requires 99 hits before completion.")
        elif location == "action":
            quest["state_contract"]["event_actions"][objective["event"]] = "Defeat 99 guards."
        else:
            quest["implementation_notes"].append("Use q99_undeclared_event to complete the objective.")
        with pytest.raises(ValueError, match="unsupported numeric detail.*99"):
            validate_generated_blueprint(bad, evidence, require_actionable=True, design_contract_version=2)
        from app.design_agent.grounding import complete_design_critique
        review = complete_design_critique({"verdict": "ready_for_review", "findings": [], "summary": "Missed by model."},
                                         bad, evidence=evidence, review_request=REQUEST)
        assert review["verdict"] == "needs_revision"
        assert any("unsupported numeric detail" in finding["issue"] for finding in review["findings"])


@pytest.mark.parametrize("allow_memory", [False, True])
def test_normal_governed_api_flow_requires_consent_confirmation_and_explicit_design_approval(audit_client, monkeypatch, allow_memory):
    client, app, db, _, tables, *_ = audit_client
    metadata = next(iter(tables.values())).metadata
    for model in (Document, DocumentChunk, DesignDecision, GameBlueprint, DesignAgentNodeExecution, DesignAgentReviewEvent):
        Table(model.__tablename__, metadata, *[
            Column(c.name, JSON() if isinstance(c.type, JSONB) else c.type, primary_key=c.primary_key,
                   server_default=None if isinstance(c.type, JSONB) else c.server_default)
            for c in model.__table__.columns])
    metadata.create_all(db.bind)
    # shortcut: only document-ID array containment; native PostgreSQL behavior needs its separate integration suite.
    def sqlite_contains(_, cursor, statement, parameters, context, executemany):
        return statement.replace("design_agent_runs.document_ids @> ?", "NOT EXISTS (SELECT 1 FROM json_each(?) AS wanted "
                                 "WHERE wanted.value NOT IN (SELECT value FROM json_each(design_agent_runs.document_ids)))"), parameters
    event.listen(db.bind, "before_cursor_execute", sqlite_contains, retval=True)
    document = Document(game_project_id="audit-a", title="Synthetic guarded-pass GDD", content_type="text/markdown", source_kind="gdd")
    db.add(document)
    db.flush()
    chunk = DocumentChunk(document_id=document.id, chunk_index=0, content=(
        "A guarded mountain pass; trust; stylized fantasy with cold mountain paths. "
        "Mira gives brief warnings. " + ("" if allow_memory else "Remember completed training objectives. ") +
        "Clear the guards and raise the Northern flag. Player health reaches zero can fail the attempt. "
        "The player explicitly confirms restarting. Runtime is deferred."))
    db.add(chunk)
    db.commit()
    chunk_id = str(chunk.id)
    content = governed_artifact()
    for section in content.values():
        section["citations"] = [chunk_id]
    for section, key in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
        for record in content[section]["content"][key]:
            record["source_chunk_ids"] = [chunk_id]
    content["unity_runtime_preview"] = {"content": {}, "citations": [], "confidence": "Low", "warnings": ["Runtime deferred."]}
    if allow_memory:
        content["npc_memory_design"] = {"content": {"rules": []}, "citations": [], "confidence": "Low",
                                        "warnings": ["NPC memory is unspecified; no continuity rules are claimed."]}
    wire = {"review_mode": "defect_detection", "summary": "Controlled offline review.", "findings": [],
            "source_coverage": {key: "deferred" if key == "unity_runtime_preview" else "covered" for key in content}}
    if allow_memory:
        wire["source_coverage"]["npc_memory_design"] = "not_specified"
    generation = copy.deepcopy(content)
    for section in generation.values():
        section["citations"] = ["S0"] if section["citations"] else []
        for key in ("npcs", "quests"):
            for record in section["content"].get(key, []):
                record["source_chunk_ids"] = ["S0"]
    replies = [{"section_queries": {key: "guarded pass " + key.replace("_", " ") for key in BLUEPRINT_SECTION_KEYS}},
               content_draft_fixture(generation), wire]
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        return _completion(json.dumps(replies[len(calls) - 1]))
    provider = NvidiaDesignAgentProvider(llm_provider=NvidiaProvider(
        base_url="https://example.test/v1", timeout_seconds=1, repair_enabled=False,
        key_reader=lambda _: "offline-only", client=httpx.Client(transport=httpx.MockTransport(respond))))
    retrievals = []
    def retrieve(section_queries=None, **kwargs):
        retrievals.append({"section_queries": section_queries, **kwargs})
        return [{"id": chunk_id, "chunk_id": chunk_id, "document_id": str(document.id), "title": document.title,
                 "content": chunk.content, "chunk_index": 0, "similarity": 0.95,
                 "matched_sections": list(BLUEPRINT_SECTION_KEYS),
                 "section_similarities": {key: 0.95 for key in BLUEPRINT_SECTION_KEYS}}]
    workflow = DesignAgentWorkflow("sqlite://", sessionmaker(bind=db.bind, expire_on_commit=False), provider,
                                   SimpleNamespace(query_lore_sections=retrieve))
    saver = InMemorySaver()
    workflow._checkpointer = lambda: nullcontext(saver)
    app.dependency_overrides[get_design_agent_service] = lambda: DesignAgentService(workflow)
    monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
    headers = {"X-Game-Project-ID": "audit-a"}
    payload = {"objective": "Review the synthetic GDD for design approval.", "document_ids": [str(document.id)],
               "defer_runtime": True, "allow_unspecified_memory": allow_memory, "hosted_provider_consent": False, "max_revisions": 2}
    assert client.post("/api/v1/design-agent/runs", headers=headers, json=payload).status_code == 409
    assert calls == []
    started = client.post("/api/v1/design-agent/runs", headers=headers, json={**payload, "hosted_provider_consent": True})
    assert started.status_code == 201, (started.text, [row.last_error for row in db.query(DesignAgentRun).filter_by(status="failed")])
    run = started.json()
    assert run["allow_unspecified_memory"] is allow_memory
    assert db.get(DesignAgentRun, UUID(run["id"])).model_config["allow_unspecified_memory"] is allow_memory
    assert run["status"] == "awaiting_review" and len(calls) == 3 and len(retrievals) == 1
    assert client.post("/api/v1/design-agent/runs", headers=headers,
                       json={**payload, "hosted_provider_consent": True}).status_code == 409
    assert len(calls) == 3
    critic_input = json.loads(calls[-1]["messages"][1]["content"].split("Input: ", 1)[1])
    assert all("warnings" in section and "confidence" not in section for section in critic_input["artifact"].values())
    artifact = run["current_artifact"]
    before_approval = copy.deepcopy(artifact["content"])
    base = f"/api/v1/design-agent/runs/{run['id']}"
    assert client.get(base + "/exports/technical-brief", headers=headers).status_code == 409
    assert client.post(base + "/review", headers=headers, json={"decision": "approve", "artifact_id": artifact["id"]}).status_code == 409
    original_artifact = copy.deepcopy(artifact)
    # A rejected no-op must preserve reviewable work and consume one bounded attempt.
    replies.append({"changes": [{"artifact_path": "/npc_archetypes/content/npcs/0/dialogue_triggers/0/text",
                                 "replacement": artifact["content"]["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["text"]}]})
    rejected = client.post(base + "/review", headers=headers, json={"decision": "reject", "artifact_id": artifact["id"],
        "reason": "Improve only the NPC speech.", "target_sections": ["npc_archetypes"]})
    assert rejected.status_code == 409, rejected.text
    saved = client.get(base, headers=headers).json()
    assert saved["status"] == "awaiting_review" and saved["revision_count"] == 1
    assert saved["current_artifact"] == original_artifact and saved["critique"] == run["critique"]
    trace = client.get(base + "/trace", headers=headers).json()
    assert any(item["node_name"] == "revise" and item["status"] == "failed" for item in trace["items"])
    assert len(calls) == 4 and len(retrievals) == 1
    targets = ["npc_archetypes", "quest_hooks"]
    patch = project_content_revision(artifact["content"], targets)
    lines = patch["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]
    lines[0]["text"] = "The pass still needs your help; finish your work there."
    lines.append({**lines[0], "trigger": None, "stage": "completion", "quest_index": 0,
                  "situation": "After clearing the guards and raising the Northern flag",
                  "text": "Guards cleared, flag raised. The pass is secure."})
    proposed_failure = "Player explicitly abandons the active attempt."
    patch["quest_hooks"]["content"]["quests"][0]["failure_states"] = [proposed_failure]
    patch["quest_hooks"]["content"]["quests"][0]["assumptions"].append(
        "Failure on voluntary abandonment is an unverified gameplay proposal.")
    replies.extend([field_revision_fixture(project_content_revision(artifact["content"], targets), patch), wire])
    revision = client.post(base + "/review", headers=headers, json={"decision": "reject", "artifact_id": artifact["id"],
        "reason": "Improve the progress line, add completion dialogue and propose failure on explicit player abandonment.",
        "target_sections": targets})
    assert revision.status_code == 200, revision.text
    run = revision.json()
    artifact = run["current_artifact"]
    assert run["status"] == "awaiting_review" and run["revision_count"] == 2
    assert len(calls) == 6 and len(retrievals) == 1
    assert all(artifact["content"][key] == original_artifact["content"][key] for key in before_approval if key not in targets)
    revised_lines = artifact["content"]["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"]
    assert revised_lines[0]["trigger"] == original_artifact["content"]["npc_archetypes"]["content"]["npcs"][0]["dialogue_triggers"][0]["trigger"]
    assert revised_lines[1]["eligibility"]["stage"] == "completion"
    state = artifact["content"]["quest_hooks"]["content"]["quests"][0]["state_contract"]
    assert state["event_actions"][state["failure"]["events"][0]] == proposed_failure
    assert db.get(DesignAgentArtifact, UUID(original_artifact["id"])).content == original_artifact["content"]
    before_approval = copy.deepcopy(artifact["content"])
    confirmations = [{key: item[key] for key in ("section", "record_id", "assumption")}
                     for item in run["critique"]["content"]["quality_scorecard"]["unresolved_assumptions"]]
    approved = client.post(base + "/review", headers=headers, json={"decision": "approve", "artifact_id": artifact["id"],
                                                                   "confirmed_proposals": confirmations})
    assert approved.status_code == 200, approved.text
    final = approved.json()
    assert final["status"] == "completed" and final["current_artifact"]["immutable"] is True
    assert final["current_artifact"]["content"]["npc_memory_design"].get("memory_unspecified", False) is allow_memory
    assert db.get(GameBlueprint, UUID(final["current_artifact"]["blueprint_id"])).status == "approved"
    assert db.get(DesignAgentArtifact, UUID(artifact["id"])).content == before_approval
    brief = client.get(base + "/exports/technical-brief", headers=headers)
    assert brief.status_code == 200 and document.title in brief.text
    assert ("**Unspecified—not assessed.**" in brief.text) is allow_memory
    npc = before_approval["npc_archetypes"]["content"]["npcs"][0]
    quest = before_approval["quest_hooks"]["content"]["quests"][0]
    assert npc["archetype"] in brief.text and npc["dialogue_triggers"][0]["text"] in brief.text
    assert all(objective in brief.text for objective in quest["objectives"])
    assert all(note in brief.text for note in npc["implementation_notes"] + quest["implementation_notes"])
    assert proposed_failure in brief.text and revised_lines[1]["text"] in brief.text
    assert client.get(base + "/exports/runtime", headers=headers).status_code == 409
    assert client.post(base + "/review", headers=headers, json={"decision": "approve"}).status_code == 409
    assert len(calls) == 6 and len(retrievals) == 1


@pytest.mark.parametrize("reviewed,final", [(True, False), (False, False), (True, True)])
def test_run_response_pairs_current_draft_with_its_own_critique(audit_client, reviewed, final):
    from uuid import uuid4

    _, _, db, _, _, ids, originals = audit_client
    run_id, _, snapshot_id, old_critique_id, _ = ids
    run = db.get(DesignAgentRun, run_id)
    draft = DesignAgentArtifact(id=uuid4(), run_id=run_id, game_project_id=run.game_project_id,
        evidence_snapshot_id=snapshot_id, version=2, artifact_type="draft", content=originals[0], immutable=False)
    db.add(draft)
    # A later timestamp on an old review must never select it for a newer draft.
    db.get(DesignAgentCritique, old_critique_id).created_at = datetime(2030, 1, 1)
    if reviewed:
        db.add(DesignAgentCritique(id=uuid4(), run_id=run_id, artifact_id=draft.id,
            game_project_id=run.game_project_id, content=originals[2], provider_name="nvidia",
            model_name="current-critic", created_at=datetime(2030, 1, 1) - timedelta(days=1)))
    if final:
        db.add(DesignAgentArtifact(id=uuid4(), run_id=run_id, game_project_id=run.game_project_id,
            evidence_snapshot_id=snapshot_id, version=3, artifact_type="final", content=originals[0], immutable=True))
    db.commit()
    response = DesignAgentService._response(db, run)
    assert response.current_artifact.version == (3 if final else 2)
    assert (response.critique.artifact_id if response.critique else None) == (draft.id if reviewed else None)
