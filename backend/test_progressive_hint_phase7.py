import pytest
import uuid
import json
import time
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective, QuestProgress
from app.models.world_state import WorldStateFlag
from app.models.telemetry import LLMTelemetryLog
from app.services.hint_engine import HintEngine, HINT_COOLDOWN_SECONDS
from app.services.graph_cache import graph_cache

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    # Clear tables just in case
    session.query(QuestProgress).delete()
    session.query(QuestObjective).delete()
    session.query(Quest).delete()
    session.query(WorldStateFlag).filter(WorldStateFlag.flag_key.like("hint:progress:%")).delete()
    session.commit()
    yield session
    # Cleanup
    session.query(QuestProgress).delete()
    session.query(QuestObjective).delete()
    session.query(Quest).delete()
    session.query(WorldStateFlag).filter(WorldStateFlag.flag_key.like("hint:progress:%")).delete()
    session.commit()
    session.close()

@pytest.fixture(scope="module")
def seeded_npc(db_session):
    npc_slug = f"hint_npc_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Hint Giver Eldrin",
        personality_summary="A wise wizard who knows the secrets of the ancient trails.",
        dialogue_style="Mysterious and brief.",
        voice_profile="soft",
        faction_alignment="mages"
    )
    db_session.add(npc)
    db_session.commit()
    db_session.refresh(npc)
    yield npc
    db_session.delete(npc)
    db_session.commit()

@pytest.fixture(scope="module")
def seeded_quest(db_session, seeded_npc):
    quest_id = uuid.uuid4()
    db_quest = Quest(
        id=quest_id,
        npc_slug=seeded_npc.slug,
        title="Find the Sacred Flame",
        description="Search for the ancient fire at the Temple of Ash.",
        difficulty="Medium",
        gold_reward=100,
        xp_reward=500
    )
    db_session.add(db_quest)

    objective = QuestObjective(
        id=uuid.uuid4(),
        quest_id=quest_id,
        objective_index=0,
        description="Defeat the Cinder Golem at Temple of Ash",
        target_type="kill",
        target_id="cinder_golem",
        quantity_required=1
    )
    db_session.add(objective)
    db_session.commit()
    db_session.refresh(db_quest)
    yield db_quest

def test_gate_h_api_validation_checks(seeded_quest):
    """Verify that invalid inputs return HTTP 422."""
    # Invalid Quest ID (non-existent UUID)
    payload = {
        "quest_id": str(uuid.uuid4()),
        "player_id": "test_player",
        "hint_level": 1
    }
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 422
    assert "Quest with ID" in res.json()["detail"]

    # Invalid Hint Level bounds (< 1)
    payload = {
        "quest_id": str(seeded_quest.id),
        "player_id": "test_player",
        "hint_level": 0
    }
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 422

    # Invalid Hint Level bounds (> 3)
    payload = {
        "quest_id": str(seeded_quest.id),
        "player_id": "test_player",
        "hint_level": 4
    }
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 422


def test_progressive_escalation_rules(db_session, seeded_quest):
    """Verify Gate A, B, C (Hint Levels 1, 2, 3) and Gate D (progression sequence)."""
    player_id = f"prog_player_{uuid.uuid4().hex[:6]}"

    # Progression Gate D: Try level 2 first (skip level 1) -> Must be rejected with HTTP 422
    payload = {
        "quest_id": str(seeded_quest.id),
        "player_id": player_id,
        "hint_level": 2
    }
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 422
    assert "Progression violation" in res.json()["detail"]

    # Gate A: Generate Level 1 Hint (Subtle) -> Deterministic
    payload["hint_level"] = 1
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["hint_level"] == 1
    assert data["spoiler_level"] == "low"
    assert "threat lurks in the wilderness" in data["hint"].lower() # deterministic string

    # Cooldown Gate E: Try level 2 immediately -> Must be blocked by cooldown (HTTP 422)
    payload["hint_level"] = 2
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 422
    assert "Cooldown active" in res.json()["detail"]

    # Cooldown Bypass (Simulate 5 minutes elapsed in database)
    flag_key = HintEngine.get_progress_flag_key(player_id, seeded_quest.id)
    flag = db_session.query(WorldStateFlag).filter(WorldStateFlag.flag_key == flag_key).first()
    assert flag is not None
    state = json.loads(flag.flag_value)
    # Set requested timestamp to 10 minutes ago
    state["last_requested_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    flag.flag_value = json.dumps(state)
    db_session.commit()

    # Gate B: Generate Level 2 Hint (Contextual) -> Deterministic/Contextual
    payload["hint_level"] = 2
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["hint_level"] == 2
    assert data["spoiler_level"] == "medium"
    assert "cinder golem" in data["hint"].lower() # contextual target name
    assert "cinder golem" in data["hint"].lower()

    # Cooldown Bypass (Simulate 5 minutes elapsed again)
    state = json.loads(flag.flag_value)
    state["last_requested_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    flag.flag_value = json.dumps(state)
    db_session.commit()

    # Gate C: Generate Level 3 Hint (Direct) -> LLM generated
    payload["hint_level"] = 3
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["hint_level"] == 3
    assert data["spoiler_level"] == "high"
    # Ensure hint content returned is non-empty
    assert len(data["hint"]) > 10

    # Gate D: Try level 3 again -> Allowed since max reached (verifies 3->3 sequence)
    # First bypass cooldown
    state = json.loads(flag.flag_value)
    state["last_requested_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    flag.flag_value = json.dumps(state)
    db_session.commit()

    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 200
    assert res.json()["hint_level"] == 3


def test_gate_f_cache_validation_behavior(db_session, seeded_quest):
    """Verify version-stamp cache hit/miss behavior."""
    player_id = f"cache_player_{uuid.uuid4().hex[:6]}"

    # Miss 1: Generate Level 1 Hint (Should record cache miss)
    payload = {
        "quest_id": str(seeded_quest.id),
        "player_id": player_id,
        "hint_level": 1
    }
    res = client.post("/api/v1/hints/generate", json=payload)
    assert res.status_code == 200

    # Wait, the request just completed, so calling again would fail on cooldown.
    # We bypass cooldown in database, but keep cache.
    flag_key = HintEngine.get_progress_flag_key(player_id, seeded_quest.id)
    flag = db_session.query(WorldStateFlag).filter(WorldStateFlag.flag_key == flag_key).first()
    state = json.loads(flag.flag_value)
    state["last_requested_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    flag.flag_value = json.dumps(state)
    db_session.commit()

    # Query same level 1 again. It should be a cache hit, returned instantly.
    res2 = client.post("/api/v1/hints/generate", json=payload)
    assert res2.status_code == 200
    assert res2.json()["hint"] == res.json()["hint"]


def test_gate_g_telemetry_persistence(db_session, seeded_quest):
    """Verify metrics correctly persist in the database logs."""
    player_id = f"telemetry_player_{uuid.uuid4().hex[:6]}"

    # Miss 1: Generate Level 1 Hint
    payload = {
        "quest_id": str(seeded_quest.id),
        "player_id": player_id,
        "hint_level": 1
    }
    client.post("/api/v1/hints/generate", json=payload)

    # Search telemetry table in PostgreSQL
    logs = db_session.query(LLMTelemetryLog).filter(
        LLMTelemetryLog.action_type == "progressive_hints_generated_total"
    ).all()
    assert len(logs) > 0


def test_hints_status_endpoint(db_session, seeded_quest):
    """Verify GET /api/v1/hints/status yields current status and cooldown."""
    player_id = f"status_player_{uuid.uuid4().hex[:6]}"

    # Initial status (current_level should be 0, cooldown_remaining_seconds should be 0)
    res = client.get(f"/api/v1/hints/status?quest_id={seeded_quest.id}&player_id={player_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["current_level"] == 0
    assert data["cooldown_remaining_seconds"] == 0

    # Generate level 1
    payload = {
        "quest_id": str(seeded_quest.id),
        "player_id": player_id,
        "hint_level": 1
    }
    client.post("/api/v1/hints/generate", json=payload)

    # Status post generation (current_level should be 1, cooldown active > 0)
    res = client.get(f"/api/v1/hints/status?quest_id={seeded_quest.id}&player_id={player_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["current_level"] == 1
    assert data["cooldown_remaining_seconds"] > 0
    assert data["cooldown_remaining_seconds"] <= HINT_COOLDOWN_SECONDS
