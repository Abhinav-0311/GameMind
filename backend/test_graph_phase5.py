import pytest
import uuid
import asyncio
import time
import concurrent.futures
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal, engine
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship, PendingIngest, RelationshipTypeRule
from app.models.telemetry import LLMTelemetryLog
from app.repositories.graph_repository import graph_repo
from app.workers.cleanup_worker import cleanup_worker_loop

client = TestClient(app)

@pytest.fixture(scope="function")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.rollback()
        # Delete created entities/relationships
        db_session.query(WorldRelationship).delete()
        db_session.query(WorldEntityVersion).delete()
        db_session.query(WorldEntity).delete()
        db_session.query(PendingIngest).delete()
        db_session.query(LLMTelemetryLog).delete()
        db_session.commit()
        db_session.close()

def test_analytics_endpoint_correctness(db):
    """Verify endpoint counts, density, degree, and top hubs."""
    # Seed 3 active nodes and 2 active relationships
    slug_a = f"node_a_{uuid.uuid4().hex[:6]}"
    slug_b = f"node_b_{uuid.uuid4().hex[:6]}"
    slug_c = f"node_c_{uuid.uuid4().hex[:6]}"

    # Add allowed taxonomy rules to db
    rule = db.query(RelationshipTypeRule).filter_by(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character").first()
    if not rule:
        rule = RelationshipTypeRule(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character")
        db.add(rule)
        db.commit()

    graph_repo.create_entity(db, slug_a, "character", "Hero A", "Alpha")
    graph_repo.create_entity(db, slug_b, "character", "Hero B", "Beta")
    graph_repo.create_entity(db, slug_c, "character", "Hero C", "Gamma")

    # Connect: A --(allied_with)--> B --(allied_with)--> C
    graph_repo.create_relationship(db, slug_a, slug_b, "allied_with")
    graph_repo.create_relationship(db, slug_b, slug_c, "allied_with")

    # Call endpoint
    res = client.get("/api/v1/graph/analytics")
    assert res.status_code == 200
    data = res.json()

    assert data["active_nodes"] == 3
    assert data["active_relationships"] == 2
    # Density for directed graph: E / (V * (V - 1)) = 2 / (3 * 2) = 2 / 6 = 0.3333333333333333
    assert abs(data["density"] - 1.0/3.0) < 1e-5
    # Max degree: B is connected to A and C, so B degree is 2. A degree is 1. C degree is 1. Max degree is 2.
    assert data["max_degree"] == 2
    # Average degree: (1 + 2 + 1) / 3 = 4 / 3 = 1.3333333333333333
    assert abs(data["average_degree"] - 4.0/3.0) < 1e-5

    # Top hubs: B should be the highest
    hubs = data["hub_nodes"]
    assert len(hubs) >= 1
    assert hubs[0]["slug"] == slug_b
    assert hubs[0]["degree"] == 2

@pytest.mark.anyio
async def test_cleanup_worker_lifecycle(db):
    """Verify that background cleanup worker prunes and cleanly stops without leaks."""
    # Seed one active and one expired pending ingest
    expired_id = uuid.uuid4()
    expired_record = PendingIngest(
        validation_id=expired_id,
        payload={"operation": "test_prune"},
        reason_blocked="Expired",
        expires_at=datetime.utcnow() - timedelta(minutes=10)
    )

    active_id = uuid.uuid4()
    active_record = PendingIngest(
        validation_id=active_id,
        payload={"operation": "test_active"},
        reason_blocked="Active",
        expires_at=datetime.utcnow() + timedelta(minutes=60)
    )

    db.add(expired_record)
    db.add(active_record)
    db.commit()

    # Track checkout counts of pool
    pool = engine.pool
    checked_out_before = pool.checkedout()

    stop_event = asyncio.Event()
    task = asyncio.create_task(cleanup_worker_loop(stop_event))

    # Allow execution loop to run once
    await asyncio.sleep(0.5)

    stop_event.set()
    await task

    # Connection checkout audit
    checked_out_after = pool.checkedout()
    assert checked_out_before == checked_out_after, "Connection leak detected in cleanup worker!"

    # Verify db state
    db.expire_all()
    expired_exists = db.query(PendingIngest).filter(PendingIngest.validation_id == expired_id).first() is not None
    active_exists = db.query(PendingIngest).filter(PendingIngest.validation_id == active_id).first() is not None

    assert not expired_exists
    assert active_exists

def test_concurrent_traversal_execution_no_deadlocks_no_leaks(db):
    """Verify that concurrent read queries complete successfully without deadlocks or connection pool leaks."""
    # Seed nodes
    slug_s = f"node_s_{uuid.uuid4().hex[:6]}"
    slug_t = f"node_t_{uuid.uuid4().hex[:6]}"
    graph_repo.create_entity(db, slug_s, "character", "Source", "S")
    graph_repo.create_entity(db, slug_t, "character", "Target", "T")
    graph_repo.create_relationship(db, slug_s, slug_t, "allied_with")

    pool = engine.pool
    checked_out_before = pool.checkedout()

    # Execute 20 concurrent paths traversal requests
    def execute_request():
        r = client.get(f"/api/v1/graph/traverse?source={slug_s}&target={slug_t}")
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(execute_request) for _ in range(20)]
        results = [f.result() for f in futures]

    # Verify all succeeded
    for status_code in results:
        assert status_code == 200

    checked_out_after = pool.checkedout()
    assert checked_out_before == checked_out_after, "Connection leak detected after concurrent execution!"
