import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective, QuestProgress
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.models.world_state import WorldStateFlag
from app.models.telemetry import LLMTelemetryLog
from sqlalchemy import text
import uuid
import datetime
import time

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        # Clear tables
        session.query(QuestProgress).delete()
        session.query(QuestObjective).delete()
        session.query(Quest).delete()
        session.query(WorldRelationship).delete()
        session.query(WorldEntityVersion).delete()
        session.query(WorldEntity).delete()
        session.query(WorldStateFlag).delete()
        session.query(NPCProfile).delete()
        session.commit()
        yield session
    finally:
        session.query(QuestProgress).delete()
        session.query(QuestObjective).delete()
        session.query(Quest).delete()
        session.query(WorldRelationship).delete()
        session.query(WorldEntityVersion).delete()
        session.query(WorldEntity).delete()
        session.query(WorldStateFlag).delete()
        session.query(NPCProfile).delete()
        session.commit()
        session.close()

# ----------------------------------------------------
# Gate A: Structured Claim Contradiction Detection
# ----------------------------------------------------
def test_gate_a_contradiction_detection(db):
    # Set up active relationship in graph: A is at war with B
    # First create entities
    ent_a = WorldEntity(id=uuid.uuid4(), slug="faction_a", entity_type="faction")
    ent_b = WorldEntity(id=uuid.uuid4(), slug="faction_b", entity_type="faction")
    db.add_all([ent_a, ent_b])
    db.commit()

    ver_a = WorldEntityVersion(entity_id=ent_a.id, version=1, name="Faction A", description="First faction")
    ver_b = WorldEntityVersion(entity_id=ent_b.id, version=1, name="Faction B", description="Second faction")
    db.add_all([ver_a, ver_b])
    db.commit()

    rel = WorldRelationship(
        source_id=ent_a.id,
        target_id=ent_b.id,
        rel_type="at_war_with",
        weight=1.0,
        version=1
    )
    db.add(rel)
    db.commit()

    # Now verify consistency of claiming they are allied_with (should fail due to at_war_with conflict)
    payload = {
        "claims": [
            {"subject": "faction_a", "predicate": "allied_with", "object": "faction_b"}
        ]
    }
    res = client.post("/api/v1/narrative/verify", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["consistent"] is False
    assert len(data["contradictions"]) > 0
    assert "Contradiction detected" in data["contradictions"][0]

    # Test limit validation
    over_limit_payload = {
        "claims": [{"subject": "a", "predicate": "b", "object": "c"} for _ in range(51)]
    }
    res = client.post("/api/v1/narrative/verify", json=over_limit_payload)
    assert res.status_code == 422
    assert "Payload exceeds maximum limit of 50 claims." in res.json()["detail"]

# ----------------------------------------------------
# Gate B: Cross-NPC Knowledge Validation
# ----------------------------------------------------
def test_gate_b_cross_npc_knowledge(db):
    # Set up NPC Profile and their knowledge
    npc = NPCProfile(
        slug="eldrin",
        name="Eldrin",
        personality_summary="Mage",
        faction_alignment="mages"
    )
    db.add(npc)
    db.commit()

    # Create faction entity in the graph
    faction_ent = WorldEntity(id=uuid.uuid4(), slug="mages", entity_type="faction")
    db.add(faction_ent)
    db.commit()

    ver_faction = WorldEntityVersion(entity_id=faction_ent.id, version=1, name="Mages", description="Mages faction")
    db.add(ver_faction)
    db.commit()

    # Set up another entity connected to the mages faction (distance = 2 from Eldrin)
    staff_ent = WorldEntity(id=uuid.uuid4(), slug="crystal_staff", entity_type="item")
    db.add(staff_ent)
    db.commit()

    ver_staff = WorldEntityVersion(entity_id=staff_ent.id, version=1, name="Crystal Staff", description="Staff of crystal")
    db.add(ver_staff)
    db.commit()

    rel_staff_faction = WorldRelationship(
        source_id=staff_ent.id,
        target_id=faction_ent.id,
        rel_type="stored_at",
        weight=1.0,
        version=1
    )
    db.add(rel_staff_faction)
    db.commit()

    # Eldrin knows "crystal_staff" (Eldrin -> mages faction -> crystal_staff)
    from app.services.cross_npc_validation import CrossNPCValidationService
    assert CrossNPCValidationService.npc_knows(db, "eldrin", "crystal_staff") is True

    # Eldrin does NOT know "far_away_island"
    island_ent = WorldEntity(id=uuid.uuid4(), slug="far_away_island", entity_type="location")
    db.add(island_ent)
    db.commit()
    ver_island = WorldEntityVersion(entity_id=island_ent.id, version=1, name="Island", description="Far away")
    db.add(ver_island)
    db.commit()

    assert CrossNPCValidationService.npc_knows(db, "eldrin", "far_away_island") is False

# ----------------------------------------------------
# Gate C: World State Propagation
# ----------------------------------------------------
def test_gate_c_world_state_propagation(db):
    # Setup connection: faction_a -> standing -> faction_b
    rel = db.query(WorldRelationship).filter(
        WorldRelationship.rel_type == "at_war_with",
        WorldRelationship.valid_to.is_(None)
    ).first()
    if rel:
        db.delete(rel)
        db.commit()

    # Register as standing relation
    rel = WorldRelationship(
        source_id=db.query(WorldEntity).filter(WorldEntity.slug == "faction_a").first().id,
        target_id=db.query(WorldEntity).filter(WorldEntity.slug == "faction_b").first().id,
        rel_type="standing",
        weight=50.0,
        version=1
    )
    db.add(rel)
    db.commit()

    from app.services.world_state_propagation import WorldStatePropagationService, PropagationLimitExceededError
    
    # Propagate standing relation weight to < 20. Should set hostilities_present flag
    modified = WorldStatePropagationService.propagate_relationship_change(
        db, "faction_a", "faction_b", "standing", 15.0
    )
    assert modified >= 1

    # Check that the hostilities_present flag was set
    flag = db.query(WorldStateFlag).filter(WorldStateFlag.flag_key == "hostilities_present").first()
    assert flag is not None
    assert flag.flag_value == "true"

    # Test limit violation (simulate by connecting a large number of nodes)
    # We will temporarily add 101 relationships to faction_a to exceed node count limits of 100
    faction_a_id = db.query(WorldEntity).filter(WorldEntity.slug == "faction_a").first().id
    for i in range(105):
        other_node = WorldEntity(id=uuid.uuid4(), slug=f"node_{i}", entity_type="faction")
        db.add(other_node)
        db.flush()
        db.add(WorldEntityVersion(entity_id=other_node.id, version=1, name=f"Node {i}", description="test node"))
        db.flush()
        db.add(WorldRelationship(
            source_id=faction_a_id,
            target_id=other_node.id,
            rel_type="standing",
            weight=50.0,
            version=1
        ))
    db.commit()

    with pytest.raises(PropagationLimitExceededError):
        WorldStatePropagationService.propagate_relationship_change(
            db, "faction_a", "faction_b", "standing", 5.0
        )

# ----------------------------------------------------
# Gate D: Quest DAG Cycle Detection & Eligibility
# ----------------------------------------------------
def test_gate_d_quest_dag_and_eligibility(db):
    # Setup clean linear quests: quest1 -> prerequisite -> quest2
    npc = db.query(NPCProfile).filter(NPCProfile.slug == "eldrin").first()

    q1 = Quest(id=uuid.uuid4(), npc_slug=npc.slug, title="First Quest", description="Start here")
    q2 = Quest(id=uuid.uuid4(), npc_slug=npc.slug, title="Second Quest", description="Complete after first")
    db.add_all([q1, q2])
    db.commit()

    # Register quest entities in graph
    qe1 = WorldEntity(id=uuid.uuid4(), slug=str(q1.id), entity_type="quest")
    qe2 = WorldEntity(id=uuid.uuid4(), slug=str(q2.id), entity_type="quest")
    db.add_all([qe1, qe2])
    db.commit()

    # Add prerequisite relationship: q1 -> prerequisite -> q2
    rel_prereq = WorldRelationship(
        source_id=qe1.id,
        target_id=qe2.id,
        rel_type="prerequisite",
        weight=1.0,
        version=1
    )
    db.add(rel_prereq)
    db.commit()

    from app.services.quest_dependency import QuestDependencyAnalyzer

    # Test eligibility: Player has not completed First Quest -> ineligible
    res = client.get(f"/api/v1/narrative/quests/{q2.id}/eligibility")
    assert res.status_code == 200
    assert res.json()["eligible"] is False
    assert "First Quest" in res.json()["reason"]

    # Cycle Detection: Add circular dependency q2 -> prerequisite -> q1
    rel_cycle = WorldRelationship(
        source_id=qe2.id,
        target_id=qe1.id,
        rel_type="prerequisite",
        weight=1.0,
        version=1
    )
    db.add(rel_cycle)
    db.commit()

    assert QuestDependencyAnalyzer.detect_cycles(db) is True

# ----------------------------------------------------
# Gate E: Event Simulation Bounds
# ----------------------------------------------------
def test_gate_e_event_simulation(db):
    # Set up event chain: ev1 -> triggers -> ev2 -> triggers -> ev3 -> triggers -> ev4 -> triggers -> ev5 -> triggers -> ev6
    # Let's create these entities
    entities = []
    for i in range(1, 8):
        ent = WorldEntity(id=uuid.uuid4(), slug=f"ev{i}", entity_type="event")
        db.add(ent)
        entities.append(ent)
    db.commit()

    for i in range(7):
        db.add(WorldEntityVersion(entity_id=entities[i].id, version=1, name=f"Event {i+1}", description="event"))
    db.commit()

    # Connect them
    for i in range(6):
        db.add(WorldRelationship(
            source_id=entities[i].id,
            target_id=entities[i+1].id,
            rel_type="triggers",
            weight=1.0,
            version=1
        ))
    db.commit()

    # Simulate path starting from ev1
    payload = {
        "starting_triggers": ["ev1"]
    }
    res = client.post("/api/v1/narrative/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["path"]) > 0
    assert "depth" in data["warnings"][0].lower() # warning about depth limit (5)
    assert data["dead_end"] is True

    # Test triggers limit validation
    over_triggers = {
        "starting_triggers": [f"ev{i}" for i in range(11)]
    }
    res = client.post("/api/v1/narrative/simulate", json=over_triggers)
    assert res.status_code == 422

# ----------------------------------------------------
# Gate F: Temporal Audit Diff Generation
# ----------------------------------------------------
def test_gate_f_temporal_audit(db):
    t_start = datetime.datetime.now(datetime.timezone.utc)
    time.sleep(1.0) # Ensure window covers changes

    # Create new entity and relationship
    aud_ent = WorldEntity(id=uuid.uuid4(), slug="audit_target", entity_type="item")
    db.add(aud_ent)
    db.commit()

    db.add(WorldEntityVersion(entity_id=aud_ent.id, version=1, name="Audit Target", description="for audit"))
    db.commit()

    time.sleep(1.0)
    t_end = datetime.datetime.now(datetime.timezone.utc)

    # Get audit diff
    res = client.get(
        "/api/v1/narrative/audit",
        params={
            "as_of_start": t_start.isoformat() + "Z",
            "as_of_end": t_end.isoformat() + "Z"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "audit_target" in data["entities_added"]

    # Test audit limit validation (> 365 days)
    res = client.get(
        "/api/v1/narrative/audit",
        params={
            "as_of_start": "2020-01-01T00:00:00Z",
            "as_of_end": "2022-01-01T00:00:00Z"
        }
    )
    assert res.status_code == 422

# ----------------------------------------------------
# Gate G: Telemetry Persistence
# ----------------------------------------------------
def test_gate_g_telemetry_persistence(db):
    # Verify that telemetry records exist for each of the checked narrative metric types
    metrics = [
        "narrative_consistency_checks_total",
        "cross_npc_validation_failures_total",
        "world_state_propagations_total",
        "quest_dependency_cycles_detected_total",
        "event_simulations_total",
        "temporal_audits_total"
    ]
    for metric in metrics:
        logs = db.query(LLMTelemetryLog).filter(LLMTelemetryLog.action_type == metric).all()
        assert len(logs) > 0
