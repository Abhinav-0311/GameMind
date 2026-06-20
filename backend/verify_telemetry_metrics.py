import sys
import uuid
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.telemetry import LLMTelemetryLog
from app.models.graph import (
    WorldEntity,
    WorldEntityVersion,
    WorldRelationship,
    RelationshipTypeRule,
    PendingIngest,
    ConsistencyOverride
)

client = TestClient(app)
db = SessionLocal()

def cleanup():
    db.rollback()
    
    # Delete test entities/relationships
    db.query(WorldRelationship).filter(
        WorldRelationship.source_id.in_(
            db.query(WorldEntity.id).filter(WorldEntity.slug.in_(["tel_hero", "tel_castle"]))
        ) | WorldRelationship.target_id.in_(
            db.query(WorldEntity.id).filter(WorldEntity.slug.in_(["tel_hero", "tel_castle"]))
        )
    ).delete(synchronize_session=False)
    
    db.query(ConsistencyOverride).delete()
    db.query(PendingIngest).delete()

    db.query(WorldEntityVersion).filter(
        WorldEntityVersion.entity_id.in_(
            db.query(WorldEntity.id).filter(WorldEntity.slug.in_(["tel_hero", "tel_castle"]))
        )
    ).delete(synchronize_session=False)

    db.query(WorldEntity).filter(WorldEntity.slug.in_(["tel_hero", "tel_castle"])).delete(synchronize_session=False)

    # Delete test taxonomy rules
    db.query(RelationshipTypeRule).filter(
        RelationshipTypeRule.rel_type == "located_in",
        RelationshipTypeRule.allowed_source_type == "NPC",
        RelationshipTypeRule.allowed_target_type == "Location"
    ).delete()

    # Clear custom graph telemetry logs to start fresh
    db.query(LLMTelemetryLog).filter(
        LLMTelemetryLog.action_type.like("graph_%")
    ).delete(synchronize_session=False)

    db.commit()

def seed_rules():
    rule = db.query(RelationshipTypeRule).filter(
        RelationshipTypeRule.rel_type == "located_in",
        RelationshipTypeRule.allowed_source_type == "NPC",
        RelationshipTypeRule.allowed_target_type == "Location"
    ).first()
    
    if not rule:
        rule = RelationshipTypeRule(
            id=uuid.uuid4(),
            rel_type="located_in",
            allowed_source_type="NPC",
            allowed_target_type="Location"
        )
        db.add(rule)
        db.commit()

try:
    print("==================================================")
    print("Testing Graph Telemetry & Analytics Endpoint")
    print("==================================================")
    
    cleanup()
    seed_rules()
    
    # 1. Create entities (should trigger graph_entity_create_total telemetry twice)
    print("\n1. Creating source NPC entity 'tel_hero'...")
    res = client.post("/api/v1/graph/entities", json={
        "slug": "tel_hero",
        "entity_type": "NPC",
        "name": "Telemetry Hero",
        "description": "NPC for telemetry validation",
        "importance_score": 50,
        "properties": {}
    })
    assert res.status_code == 201
    
    print("2. Creating target Location entity 'tel_castle'...")
    res = client.post("/api/v1/graph/entities", json={
        "slug": "tel_castle",
        "entity_type": "Location",
        "name": "Telemetry Castle",
        "description": "Location for telemetry validation",
        "importance_score": 60,
        "properties": {}
    })
    assert res.status_code == 201

    # 3. Create valid relationship (should trigger graph_relationship_create_total)
    print("\n3. Creating valid relationship 'located_in' (tel_hero -> tel_castle)...")
    res = client.post("/api/v1/graph/relationships", json={
        "source_slug": "tel_hero",
        "target_slug": "tel_castle",
        "rel_type": "located_in",
        "weight": 1.0,
        "properties": {}
    })
    assert res.status_code == 201

    # 4. Trigger validation failures (should trigger graph_validation_failure_total)
    print("\n4. Triggering duplicate relationship creation (fails validation)...")
    res = client.post("/api/v1/graph/relationships", json={
        "source_slug": "tel_hero",
        "target_slug": "tel_castle",
        "rel_type": "located_in",
        "weight": 1.0,
        "properties": {}
    })
    assert res.status_code == 422
    
    print("\n5. Triggering invalid taxonomy relationship (fails validation)...")
    res = client.post("/api/v1/graph/relationships", json={
        "source_slug": "tel_castle",
        "target_slug": "tel_hero",
        "rel_type": "located_in",
        "weight": 1.0,
        "properties": {}
    })
    assert res.status_code == 422
    val_id = res.json()["detail"]["validation_id"]

    # 5. Apply consistency override (should trigger graph_override_total)
    print(f"\n6. Applying consistency override for validation ID '{val_id}'...")
    res = client.post("/api/v1/consistency/override", json={
        "validation_id": val_id,
        "override_applied_by": "metrics_test_admin",
        "override_reason": "Bypassing for metrics check"
    })
    assert res.status_code == 200

    # 6. Retrieve overview graph analytics from GET /api/v1/analytics/graph
    print("\n7. Fetching metrics from GET /api/v1/analytics/graph...")
    res = client.get("/api/v1/analytics/graph")
    print(f"Status Code: {res.status_code}")
    metrics = res.json()
    import json
    print(f"Metrics Output:\n{json.dumps(metrics, indent=2)}")
    
    # Assert values
    assert metrics["graph_entity_create_total"] == 2
    assert metrics["graph_relationship_create_total"] == 1
    assert metrics["graph_validation_failure_total"] == 2
    assert metrics["graph_override_total"] == 1
    assert metrics["graph_pending_ingest_count"] == 1  # 1 pending ingest from duplicate check is still in queue, override check was deleted
    assert metrics["graph_schema_lock_wait_seconds"] >= 0.0

    # 7. Check raw telemetry entries in DB
    print("\n8. Verifying records inside the 'llm_telemetry_logs' database table...")
    db.expire_all()
    logs = db.query(LLMTelemetryLog).filter(LLMTelemetryLog.action_type.like("graph_%")).all()
    print(f"Found {len(logs)} graph logs in DB:")
    for log in logs:
        print(f"  - Action: '{log.action_type}', NPC/Slug: '{log.npc_slug}', Model/Type: '{log.model_used}', LatencyMs: {log.latency_ms}")
        
    print("\n==================================================")
    print("ALL TELEMETRY TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

finally:
    db.close()
