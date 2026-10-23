"""Finding-review audit API against disposable SQLite; no main/lifespan/conftest."""
import copy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, ForeignKeyConstraint, JSON, MetaData, Table, UniqueConstraint, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.design_agent import router
from app.database import get_db
from app.dependencies import get_current_user
from app.models import design_agent as models
from app.models.user import ProjectMembership, User


@pytest.fixture
def audit_client():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    metadata = MetaData()
    classes = [models.DesignAgentRun, models.DesignAgentArtifact, models.DesignAgentCritique,
               models.DesignAgentEvidenceSnapshot, User, ProjectMembership]
    resolution = getattr(models, "DesignAgentFindingResolution", None)
    if resolution is not None:
        classes.append(resolution)
    tables = {}
    for model in classes:
        tables[model] = Table(model.__tablename__, metadata, *[
            Column(c.name, JSON() if isinstance(c.type, JSONB) else c.type,
                   primary_key=c.primary_key, server_default=None if isinstance(c.type, JSONB) else c.server_default)
            for c in model.__table__.columns
        ], *[UniqueConstraint(*(c.name for c in constraint.columns))
             for constraint in model.__table__.constraints if isinstance(constraint, UniqueConstraint)])
    if resolution is not None:
        for constraint in resolution.__table__.foreign_key_constraints:
            tables[resolution].append_constraint(ForeignKeyConstraint(
                [element.parent.name for element in constraint.elements],
                [element.target_fullname for element in constraint.elements], ondelete=constraint.ondelete))
    metadata.create_all(engine)
    run, artifact, snapshot, critique, user = [uuid4() for _ in range(5)]
    now = datetime.now(timezone.utc)
    content = {"npc_archetypes": {"content": {"npcs": [{"name": "Mira", "dialogue_style": "formal, slow"}]}}}
    evidence = [{"chunk_id": "frozen-1", "content": "Mira speaks in a formal and slow manner.", "title": "GDD"}]
    review = {"verdict": "needs_revision", "summary": "Punctuation differs.", "findings": [
        {"section": "npc_archetypes", "severity": "high", "issue": "Comma differs from and.",
         "recommendation": "Replace the comma with and."}]}
    with engine.begin() as connection:
        connection.execute(tables[User].insert().values(id=user, email="reviewer@example.test", is_active=True))
        connection.execute(tables[ProjectMembership].insert().values(
            id=uuid4(), user_id=user, game_project_id="audit-a", role="editor"))
        connection.execute(tables[models.DesignAgentRun].insert().values(
            id=run, game_project_id="audit-a", objective="Review Mira against the frozen GDD.",
            status="awaiting_review", current_node="human_review", revision_count=0,
            max_revisions=1, model_config={}, document_ids=[], created_at=now, updated_at=now))
        connection.execute(tables[models.DesignAgentEvidenceSnapshot].insert().values(
            id=snapshot, run_id=run, game_project_id="audit-a", items=evidence, revision=1))
        connection.execute(tables[models.DesignAgentArtifact].insert().values(
            id=artifact, run_id=run, game_project_id="audit-a", evidence_snapshot_id=snapshot,
            version=1, content=content, immutable=False, artifact_type="draft", created_at=now))
        connection.execute(tables[models.DesignAgentCritique].insert().values(
            id=critique, run_id=run, artifact_id=artifact, game_project_id="audit-a", content=review,
            provider_name="nvidia", model_name="saved-critic", created_at=now))
    session = Session(engine)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: session.get(User, user)
    url = f"/api/v1/design-agent/runs/{run}/artifacts/{artifact}/finding-resolutions"
    with TestClient(app) as client:
        yield client, app, session, url, tables, (run, artifact, snapshot, critique, user), (content, evidence, review)
    session.close()
    engine.dispose()


def submission(client, url):
    response = client.get(url, headers={"X-Game-Project-ID": "audit-a"})
    assert response.status_code == 200, response.text
    catalog = response.json()
    return {key: catalog[key] for key in (
        "critique_id", "critique_sha256", "artifact_sha256", "evidence_sha256") } | {
        "finding_id": catalog["findings"][0]["finding_id"],
        "reason": "The cited passage supports both voice traits; punctuation does not change their meaning.",
        "artifact_path": "/npc_archetypes/content/npcs/0/dialogue_style",
        "evidence_chunk_id": "frozen-1", "evidence_quote": "Mira speaks in a formal and slow manner.",
    }


def post(client, url, payload):
    return client.post(url, headers={"X-Game-Project-ID": "audit-a"}, json=payload)


def test_resolution_is_audited_and_does_not_change_draft_critic_or_run(audit_client):
    client, _, db, url, tables, ids, originals = audit_client
    payload = submission(client, url)
    response = post(client, url, payload)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["reviewer_user_id"] == str(ids[4])
    assert record["reviewer_label"] == "reviewer@example.test"
    assert record["disposition"] == "not_a_defect" and record["approval_effect"] == "none"
    assert record["artifact_value"] == "formal, slow"
    assert record["created_at"]
    db.expire_all()
    assert db.get(models.DesignAgentArtifact, ids[1]).content == originals[0]
    assert db.get(models.DesignAgentEvidenceSnapshot, ids[2]).items == originals[1]
    assert db.get(models.DesignAgentCritique, ids[3]).content == originals[2]
    run = db.get(models.DesignAgentRun, ids[0])
    assert (run.status, run.current_node, run.revision_count) == ("awaiting_review", "human_review", 0)
    assert db.get(models.DesignAgentArtifact, ids[1]).blueprint_id is None
    db.close()  # a new session must read the persisted record
    catalog = client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()
    assert catalog["resolutions"][0]["id"] == record["id"]
    assert catalog["findings"][0]["finding"] == originals[2]["findings"][0]


def test_viewer_can_read_but_owner_can_record(audit_client):
    client, _, db, url, *_ = audit_client
    payload = submission(client, url)
    membership = db.query(ProjectMembership).one()
    membership.role = "viewer"
    db.commit()
    assert client.get(url, headers={"X-Game-Project-ID": "audit-a"}).status_code == 200
    membership.role = "owner"
    db.commit()
    assert post(client, url, payload).status_code == 201


def test_exact_retry_is_idempotent_but_cannot_rewrite_audit_record(audit_client):
    client, _, _, url, *_ = audit_client
    payload = submission(client, url)
    first = post(client, url, payload)
    assert first.status_code == 201
    assert post(client, url, payload).json()["id"] == first.json()["id"]
    changed = {**payload, "reason": "A different explanation must not overwrite the existing review record."}
    assert post(client, url, changed).status_code == 409
    assert len(client.get(url, headers={"X-Game-Project-ID": "audit-a"}).json()["resolutions"]) == 1


@pytest.mark.parametrize("field", ["critique_sha256", "artifact_sha256", "evidence_sha256", "finding_id"])
def test_stale_or_unknown_identity_is_rejected(audit_client, field):
    client, _, _, url, *_ = audit_client
    payload = submission(client, url)
    payload[field] = "0" * 64
    assert post(client, url, payload).status_code == 409


@pytest.mark.parametrize("change,expected", [
    ({"reason": "   "}, 422), ({"evidence_quote": "Invented source passage."}, 422),
    ({"evidence_chunk_id": "foreign-chunk"}, 422), ({"artifact_path": "/missing/value"}, 422),
    ({"artifact_path": "/npc_archetypes/content/npcs/-1/dialogue_style"}, 422),
    ({"artifact_path": "/npc_archetypes/content/npcs/00/dialogue_style"}, 422),
    ({"artifact_path": "/bad~2escape"}, 422), ({"reviewer_user_id": str(uuid4())}, 422),
])
def test_invalid_or_forged_evidence_and_actor_are_rejected(audit_client, change, expected):
    client, _, _, url, *_ = audit_client
    assert post(client, url, submission(client, url) | change).status_code == expected


@pytest.mark.parametrize("role", ["viewer", "outsider", "anonymous"])
def test_write_requires_authenticated_project_editor(audit_client, role):
    client, app, db, url, _, ids, _ = audit_client
    payload = submission(client, url)
    membership = db.query(ProjectMembership).one()
    if role == "anonymous":
        app.dependency_overrides[get_current_user] = lambda: None
    elif role == "outsider":
        db.delete(membership)
        db.commit()
    else:
        membership.role = role
        db.commit()
    assert post(client, url, payload).status_code == (401 if role == "anonymous" else 403)


def test_cross_workspace_run_and_artifact_are_not_exposed(audit_client):
    client, _, _, url, *_ = audit_client
    payload = submission(client, url)
    assert post(client, url.replace(url.split("/")[5], str(uuid4())), payload).status_code == 404
    assert post(client, url.replace(url.split("/")[7], str(uuid4())), payload).status_code == 404


@pytest.mark.parametrize("change", ["new-draft", "changed-draft", "changed-evidence", "changed-critic", "not-reviewable", "immutable"])
def test_rechecks_current_state_before_recording(audit_client, change):
    client, _, db, url, tables, ids, _ = audit_client
    payload = submission(client, url)
    if change == "new-draft":
        db.execute(tables[models.DesignAgentArtifact].insert().values(
            id=uuid4(), run_id=ids[0], game_project_id="audit-a", version=2, content={},
            evidence_snapshot_id=ids[2], created_at=datetime.now(timezone.utc)))
    elif change == "changed-draft":
        db.get(models.DesignAgentArtifact, ids[1]).content = {"edited": "draft"}
    elif change == "changed-evidence":
        db.get(models.DesignAgentEvidenceSnapshot, ids[2]).items = [{"chunk_id": "frozen-1", "content": "Changed."}]
    elif change == "changed-critic":
        review = copy.deepcopy(db.get(models.DesignAgentCritique, ids[3]).content)
        review["summary"] = "Different review."
        db.get(models.DesignAgentCritique, ids[3]).content = review
    elif change == "not-reviewable":
        db.get(models.DesignAgentRun, ids[0]).status = "review_queued"
    else:
        db.get(models.DesignAgentArtifact, ids[1]).immutable = True
    db.commit()
    assert post(client, url, payload).status_code == 409


def test_record_never_relaxes_existing_approval_validator(audit_client):
    from app.design_agent.grounding import validate_design_approval
    client, _, db, url, _, ids, originals = audit_client
    assert post(client, url, submission(client, url)).status_code == 201
    critique = db.get(models.DesignAgentCritique, ids[3]).content
    with pytest.raises(ValueError, match="Independent critique must be resolved"):
        validate_design_approval(originals[0], originals[1], critique)


def test_database_constraint_rejects_cross_workspace_audit_record(audit_client):
    client, _, db, url, tables, _, _ = audit_client
    assert post(client, url, submission(client, url)).status_code == 201
    table = tables[models.DesignAgentFindingResolution]
    record = dict(db.execute(table.select()).mappings().one())
    record.update(id=uuid4(), finding_id="1" * 64, game_project_id="foreign-workspace")
    with pytest.raises(IntegrityError):
        db.execute(table.insert().values(**record))
    db.rollback()
