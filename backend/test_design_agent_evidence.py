"""Frozen evidence reads against disposable in-memory tables; no app lifespan."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Column, JSON, MetaData, Table, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.design_agent import router
from app.database import get_db
from app.dependencies import get_current_user
from app.models.design_agent import DesignAgentArtifact, DesignAgentEvidenceSnapshot, DesignAgentRun


@pytest.fixture
def evidence_client():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata = MetaData()
    tables = {}
    # Clone only the columns needed by ORM reads; do not touch production metadata.
    for model in (DesignAgentRun, DesignAgentArtifact, DesignAgentEvidenceSnapshot):
        tables[model] = Table(model.__tablename__, metadata, *[
            Column(c.name, JSON() if isinstance(c.type, JSONB) else c.type, primary_key=c.primary_key)
            for c in model.__table__.columns
        ])
    metadata.create_all(engine)
    run_id, artifact_id, snapshot_id, other_run, other_artifact, other_snapshot = [uuid4() for _ in range(6)]
    broken_links = {"foreign-snapshot": uuid4(), "missing-snapshot": uuid4()}
    with engine.begin() as conn:
        for project, run, artifact, snapshot, revision, text in [
            ("workspace-a", run_id, artifact_id, snapshot_id, 1, "Original frozen text. <script>not executable</script>"),
            ("workspace-b", other_run, other_artifact, other_snapshot, 9, "Private other-workspace evidence."),
        ]:
            conn.execute(tables[DesignAgentRun].insert().values(
                id=run, game_project_id=project, document_ids=["source"], retrieval_revision=99,
            ))
            conn.execute(tables[DesignAgentEvidenceSnapshot].insert().values(
                id=snapshot, run_id=run, game_project_id=project, revision=revision,
                items=[{"chunk_id": "chunk-1", "document_id": "source", "title": "Original GDD",
                        "content": text, "chunk_index": 0, "internal_debug": "do not expose"}],
            ))
            conn.execute(tables[DesignAgentArtifact].insert().values(
                id=artifact, run_id=run, game_project_id=project, evidence_snapshot_id=snapshot,
                version=1, content={}, created_at=datetime.now(timezone.utc),
            ))
        # A newer snapshot must not replace the artifact's original evidence.
        conn.execute(tables[DesignAgentEvidenceSnapshot].insert().values(
            id=uuid4(), run_id=run_id, game_project_id="workspace-a", revision=99,
            items=[{"chunk_id": "chunk-1", "content": "Newer replacement text."}],
        ))
        for case, broken_id in broken_links.items():
            conn.execute(tables[DesignAgentArtifact].insert().values(
                id=broken_id, run_id=run_id, game_project_id="workspace-a",
                evidence_snapshot_id=other_snapshot if case == "foreign-snapshot" else uuid4(),
                version=2, content={}, created_at=datetime.now(timezone.utc),
            ))
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    session = Session(engine)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: None

    def forbid_writes(conn, cursor, statement, parameters, context, executemany):
        assert statement.lstrip().upper().startswith("SELECT"), statement

    event.listen(engine, "before_cursor_execute", forbid_writes)
    with TestClient(app) as client:
        yield client, app, run_id, artifact_id, other_run, other_artifact, broken_links
    session.close()
    engine.dispose()


def test_frozen_evidence_uses_exact_artifact_snapshot_and_safe_projection(evidence_client):
    client, _, run_id, artifact_id, *_ = evidence_client
    response = client.get(f"/api/v1/design-agent/runs/{run_id}/artifacts/{artifact_id}/evidence",
                          headers={"X-Game-Project-ID": "workspace-a"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["artifact_id"] == str(artifact_id)
    assert result["revision"] == 1
    assert result["items"] == [{"chunk_id": "chunk-1", "document_id": "source", "title": "Original GDD",
                                "content": "Original frozen text. <script>not executable</script>", "chunk_index": 0}]


@pytest.mark.parametrize("case", ["foreign-run", "foreign-artifact", "missing-artifact", "foreign-snapshot", "missing-snapshot"])
def test_frozen_evidence_rejects_cross_workspace_or_unlinked_artifacts(evidence_client, case):
    client, _, run_id, artifact_id, other_run, other_artifact, broken_links = evidence_client
    if case == "foreign-run":
        run_id, artifact_id = other_run, other_artifact
    elif case == "foreign-artifact":
        artifact_id = other_artifact
    elif case == "missing-artifact":
        artifact_id = uuid4()
    else:
        artifact_id = broken_links[case]
    response = client.get(f"/api/v1/design-agent/runs/{run_id}/artifacts/{artifact_id}/evidence",
                          headers={"X-Game-Project-ID": "workspace-a"})
    assert response.status_code == 404
    assert "Private other-workspace evidence" not in response.text


def test_frozen_evidence_keeps_auth_dependency(evidence_client):
    client, app, run_id, artifact_id, *_ = evidence_client
    def deny():
        raise HTTPException(status_code=401, detail="Sign in is required.")
    app.dependency_overrides[get_current_user] = deny
    response = client.get(f"/api/v1/design-agent/runs/{run_id}/artifacts/{artifact_id}/evidence")
    assert response.status_code == 401


def test_trace_projection_preserves_fields_costs_nulls_and_workspace_filter():
    from decimal import Decimal
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.design_agent.service import DesignAgentService
    from app.models.design_agent import DesignAgentNodeExecution

    run_id, row_id = uuid4(), uuid4()
    started = datetime(2026, 10, 13, tzinfo=timezone.utc)
    values = dict(id=row_id, node_name="critique", attempt=2, status="running",
                  provider_name=None, model_name=None, latency_ms=17, input_tokens=31,
                  output_tokens=7, cost_usd=Decimal("0.012345"), details={"safe": "detail"},
                  error=None, started_at=started, completed_at=None)
    row = DesignAgentNodeExecution(**values)
    row.internal_debug = "do not expose"
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value.order_by.return_value.all.return_value = [row]
    service = DesignAgentService()
    service._get_run = MagicMock(return_value=SimpleNamespace(id=run_id, status="running"))
    result = service.trace(db, run_id, "workspace-a")
    assert result.model_dump(mode="json") == {
        "run_id": str(run_id), "status": "running",
        "items": [{**values, "id": str(row_id), "cost_usd": 0.012345,
                   "started_at": "2026-10-13T00:00:00Z"}],
    }
    service._get_run.assert_called_once_with(db, run_id, "workspace-a")
    db.query.assert_called_once_with(DesignAgentNodeExecution)
    conditions = query.filter.call_args.args
    assert conditions[0].compare(DesignAgentNodeExecution.run_id == run_id)
    assert conditions[1].compare(DesignAgentNodeExecution.game_project_id == "workspace-a")
    query.filter.return_value.order_by.assert_called_once_with(
        DesignAgentNodeExecution.started_at, DesignAgentNodeExecution.attempt)
    query.filter.return_value.order_by.return_value.all.return_value = []
    assert service.trace(db, run_id, "workspace-a").items == []
    db.commit.assert_not_called()
    db.add.assert_not_called()
