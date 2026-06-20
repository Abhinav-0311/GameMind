import pytest
import uuid
import datetime
import time
import threading
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective, QuestProgress
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.models.world_state import WorldStateFlag
from app.models.telemetry import LLMTelemetryLog
from sqlalchemy import text

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
# Gate 1: Event Scheduler Trigger Verification
# ----------------------------------------------------
def test_gate_1_scheduler_trigger(db):
    # Setup: Create Faction entities
    fac_a = WorldEntity(id=uuid.uuid4(), slug="sched_faction_a", entity_type="faction")
    fac_b = WorldEntity(id=uuid.uuid4(), slug="sched_faction_b", entity_type="faction")
    db.add_all([fac_a, fac_b])
    db.commit()
    db.add_all([
        WorldEntityVersion(entity_id=fac_a.id, version=1, name="Sched Faction A", description=""),
        WorldEntityVersion(entity_id=fac_b.id, version=1, name="Sched Faction B", description="")
    ])
    db.commit()

    # Create active standing relationship
    rel = WorldRelationship(
        source_id=fac_a.id,
        target_id=fac_b.id,
        rel_type="standing",
        weight=15.0, # Below 30 condition threshold
        version=1
    )
    db.add(rel)
    db.commit()

    # Create an event template that triggers when standing is below 30
    temp = WorldEntity(id=uuid.uuid4(), slug="war_breakout_template", entity_type="event_template")
    db.add(temp)
    db.commit()
    
    properties = {
        "conditions": {
            "standing_below": {
                "source": "sched_faction_a",
                "target": "sched_faction_b",
                "value": 30.0
            }
        },
        "effects": {
            "standing_shift": {
                "source": "sched_faction_a",
                "target": "sched_faction_b",
                "delta": -10.0
            }
        }
    }
    ver = WorldEntityVersion(entity_id=temp.id, version=1, name="War Breakout Template", description="", properties=properties)
    db.add(ver)
    db.commit()

    from app.services.event_scheduler import WorldEventScheduler
    triggered = WorldEventScheduler.evaluate_triggers(db, datetime.datetime.now())
    
    assert len(triggered) == 1
    assert triggered[0]["slug"] == "war_breakout_template"

# ----------------------------------------------------
# Gate 2: Narrative Orchestration Chain Limits
# ----------------------------------------------------
def test_gate_2_orchestration_limits(db):
    # Setup recursive event templates: chain1 -> chain2 -> chain3 -> chain4 -> chain5
    temps = []
    for i in range(1, 6):
        temp = WorldEntity(id=uuid.uuid4(), slug=f"chain_temp_{i}", entity_type="event_template")
        db.add(temp)
        temps.append(temp)
    db.commit()

    for i in range(5):
        # chain_temp_i chains to chain_temp_{i+1}
        props = {}
        if i < 4:
            props["chained_events"] = [f"chain_temp_{i+2}"]
        # Prevent chain_temp_2..5 from triggering at depth 1 via evaluate_triggers
        if i > 0:
            props["conditions"] = {
                "standing_below": {
                    "source": "nonexistent_faction_a",
                    "target": "nonexistent_faction_b",
                    "value": -100.0
                }
            }
        ver = WorldEntityVersion(entity_id=temps[i].id, version=1, name=f"Chain Temp {i+1}", description="", properties=props)
        db.add(ver)
    db.commit()

    from app.services.narrative_orchestrator import NarrativeOrchestrator
    # First, let's execute the orchestrator with chain_temp_1 triggering (as it has no conditions)
    res = NarrativeOrchestrator.execute_tick(db, datetime.datetime.now())
    
    # "chain_temp_1", "chain_temp_2", "chain_temp_3" should execute (depth <= 3)
    # chain_temp_4 should be pruned because depth would reach 4
    assert "chain_temp_1" in res["executed_events"]
    assert "chain_temp_2" in res["executed_events"]
    assert "chain_temp_3" in res["executed_events"]
    assert "chain_temp_4" not in res["executed_events"]
    assert res["pruned_events_count"] > 0
    assert any("depth" in w for w in res["warnings"])

# ----------------------------------------------------
# Gate 3: Faction Propagation Correctness
# ----------------------------------------------------
def test_gate_3_faction_propagation(db):
    # Reset standing relationship to 15.0 to isolate from previous tests
    from app.repositories.graph_repository import graph_repo
    active_rel = graph_repo.get_active_relationship(db, "sched_faction_a", "sched_faction_b", "standing")
    if active_rel:
        graph_repo.update_relationship(db, "sched_faction_a", "sched_faction_b", "standing", weight=15.0)
    else:
        graph_repo.create_relationship(db, "sched_faction_a", "sched_faction_b", "standing", weight=15.0)

    # Set up standing relationship: faction_a <-> faction_b
    fac_a = db.query(WorldEntity).filter(WorldEntity.slug == "sched_faction_a").first()
    fac_b = db.query(WorldEntity).filter(WorldEntity.slug == "sched_faction_b").first()
    
    # Update standing to 80 (allies)
    from app.services.faction_dynamics import FactionDynamicsEngine
    res = FactionDynamicsEngine.shift_standing(db, "sched_faction_a", "sched_faction_b", 65.0) # 15 + 65 = 80
    assert res["new_standing"] == 80.0

    # Propagate reputation: shift player's standing with faction_a. Should affect faction_b
    # Create player entity
    player = WorldEntity(id=uuid.uuid4(), slug="player_hero", entity_type="character")
    db.add(player)
    db.commit()
    db.add(WorldEntityVersion(entity_id=player.id, version=1, name="Player Hero", description=""))
    db.commit()

    # Shift standing with faction_a by +20
    updates = FactionDynamicsEngine.propagate_reputation(db, "sched_faction_a", "player_hero", 20.0)
    assert updates >= 2 # Updated sched_faction_a reputation AND propagated to ally sched_faction_b

    # Verify sched_faction_b reputation increased by 50% of 20 = 10 (base 50 + 10 = 60)
    rep_b = graph_repo.get_active_relationship(db, "sched_faction_b", "player_hero", "reputation")
    assert rep_b is not None
    assert rep_b.weight == 60.0

# ----------------------------------------------------
# Gate 4: Forecast Confidence Validation
# ----------------------------------------------------
def test_gate_4_forecast_confidence(db):
    from app.services.narrative_forecasting import NarrativeForecaster
    trends = NarrativeForecaster.forecast_trends(db, steps=3)
    assert len(trends) > 0
    for trend in trends:
        assert 0.0 <= trend["confidence_score"] <= 1.0
        assert trend["predicted_state_change"] is not None

# ----------------------------------------------------
# Gate 5: Concurrent Faction Update Locking Verification
# ----------------------------------------------------
def test_gate_5_concurrent_updates(db):
    errors = []
    
    def thread_func(delta):
        # Creates its own local DB session for concurrency simulation
        local_db = SessionLocal()
        try:
            from app.services.faction_dynamics import FactionDynamicsEngine
            FactionDynamicsEngine.shift_standing(local_db, "sched_faction_a", "sched_faction_b", delta)
        except Exception as e:
            errors.append(e)
        finally:
            local_db.close()

    # Launch two concurrent threads shifting the same standings
    t1 = threading.Thread(target=thread_func, args=(5.0,))
    t2 = threading.Thread(target=thread_func, args=(-10.0,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Confirms zero lock violations or failures
    assert len(errors) == 0

# ----------------------------------------------------
# Gate 6: Telemetry Persistence Verification
# ----------------------------------------------------
def test_gate_6_telemetry_persistence(db):
    metrics = [
        "narrative_events_triggered_total",
        "narrative_events_pruned_total",
        "faction_standing_changes_total",
        "faction_propagation_updates_total",
        "narrative_forecasts_generated_total",
        "narrative_forecast_depth_reached",
        "narrative_orchestration_duration_seconds",
        "narrative_scheduler_duration_seconds"
    ]
    for metric in metrics:
        logs = db.query(LLMTelemetryLog).filter(LLMTelemetryLog.action_type == metric).all()
        assert len(logs) > 0

# ----------------------------------------------------
# Gate 7: API Endpoint Verification
# ----------------------------------------------------
def test_gate_7_api_endpoints():
    # 1. POST /api/v1/narrative/orchestrate/tick
    res = client.post("/api/v1/narrative/orchestrate/tick")
    assert res.status_code == 200
    assert "executed_events" in res.json()

    # 2. POST /api/v1/narrative/factions/standing
    payload = {
        "faction_a": "sched_faction_a",
        "faction_b": "sched_faction_b",
        "delta": 5.0
    }
    res = client.post("/api/v1/narrative/factions/standing", json=payload)
    assert res.status_code == 200
    assert res.json()["new_standing"] is not None

    # 3. GET /api/v1/narrative/forecast
    res = client.get("/api/v1/narrative/forecast", params={"steps": 3})
    assert res.status_code == 200
    assert len(res.json()) > 0

    # Test limit validation
    res = client.get("/api/v1/narrative/forecast", params={"steps": 10})
    assert res.status_code == 422
