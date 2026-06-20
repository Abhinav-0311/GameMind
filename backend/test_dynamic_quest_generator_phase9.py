import pytest
import uuid
import time
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective, QuestProgress, GeneratedQuest
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.models.world_state import WorldStateFlag
from app.models.telemetry import LLMTelemetryLog
from app.services.graph_cache import graph_cache
from app.services.dynamic_quest_generator import DynamicQuestGenerator
from app.services.quest_template_engine import QuestTemplateEngine
from app.services.quest_validation_engine import QuestValidationEngine
from app.services.quest_narrative_composer import QuestNarrativeComposer

client = TestClient(app)

@pytest.fixture(scope="function")
def db():
    session = SessionLocal()
    try:
        # Clear tables first
        session.query(QuestProgress).delete()
        session.query(QuestObjective).delete()
        session.query(Quest).delete()
        session.query(GeneratedQuest).delete()
        session.query(WorldRelationship).delete()
        session.query(WorldEntityVersion).delete()
        session.query(WorldEntity).delete()
        session.query(WorldStateFlag).delete()
        session.query(NPCProfile).delete()
        session.query(LLMTelemetryLog).delete()
        session.commit()
        yield session
    finally:
        session.query(QuestProgress).delete()
        session.query(QuestObjective).delete()
        session.query(Quest).delete()
        session.query(GeneratedQuest).delete()
        session.query(WorldRelationship).delete()
        session.query(WorldEntityVersion).delete()
        session.query(WorldEntity).delete()
        session.query(WorldStateFlag).delete()
        session.query(NPCProfile).delete()
        session.query(LLMTelemetryLog).delete()
        session.commit()
        session.close()

# Helper to create basic entities
def setup_npc_helper(db_sess, name="Eldrin", slug="eldrin", faction="mages"):
    npc = NPCProfile(
        slug=slug,
        name=name,
        personality_summary="Mage of the Order",
        faction_alignment=faction
    )
    db_sess.add(npc)
    db_sess.commit()

    ent = WorldEntity(id=uuid.uuid4(), slug=slug, entity_type="npc")
    db_sess.add(ent)
    db_sess.commit()

    ver = WorldEntityVersion(
        entity_id=ent.id,
        version=1,
        name=name,
        description="Mage npc",
        importance_score=8
    )
    db_sess.add(ver)
    db_sess.commit()
    return npc


# ----------------------------------------------------
# Gate A: Quest Generation Correctness
# ----------------------------------------------------
def test_gate_a_quest_generation_correctness(db):
    setup_npc_helper(db, name="Eldrin", slug="eldrin")

    quest = DynamicQuestGenerator.generate_quest(
        db=db,
        npc_slug="eldrin",
        player_id="player1",
        player_level=10
    )

    assert "title" in quest
    assert "description" in quest
    assert "difficulty" in quest
    assert len(quest["objectives"]) >= 1
    assert "gold" in quest["rewards"]
    assert "xp" in quest["rewards"]
    assert "branches" in quest
    assert "consequences" in quest
    assert len(quest["branches"]) <= 5
    assert len(quest["consequences"]) <= 10


# ----------------------------------------------------
# Gate B: Template Selection
# ----------------------------------------------------
def test_gate_b_template_selection():
    # Select template by target_type
    temp_kill = QuestTemplateEngine.select_template("kill")
    assert temp_kill["target_type"] == "kill"

    temp_retrieve = QuestTemplateEngine.select_template("retrieve")
    assert temp_retrieve["target_type"] == "retrieve"

    # Selection fallback
    temp_fallback = QuestTemplateEngine.select_template("unknown_action")
    assert temp_fallback is not None


# ----------------------------------------------------
# Gate C: Narrative Consistency
# ----------------------------------------------------
def test_gate_c_narrative_consistency(db):
    setup_npc_helper(db, name="Eldrin", slug="eldrin")
    # Valid quest check should pass consistency
    quest_payload = {
        "npc_slug": "eldrin",
        "title": "Clean the Mage Tower",
        "description": "Clear out the dust",
        "difficulty": "Easy",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Clean the desks",
                "target_type": "retrieve",
                "target_id": "cleaning_duster",
                "quantity_required": 1
            }
        ],
        "rewards": {"gold": 10, "xp": 10, "items": []}
    }
    valid, reasons = QuestValidationEngine.validate_quest(db, quest_payload)
    assert valid is True
    assert len(reasons) == 0


# ----------------------------------------------------
# Gate D: Duplicate Prevention
# ----------------------------------------------------
def test_gate_d_duplicate_prevention(db):
    setup_npc_helper(db, name="Eldrin", slug="eldrin")
    quest_payload = {
        "npc_slug": "eldrin",
        "title": "Unique Quest Title",
        "description": "Some description",
        "difficulty": "Easy",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Find the key",
                "target_type": "retrieve",
                "target_id": "mystic_key",
                "quantity_required": 1
            }
        ],
        "rewards": {"gold": 10, "xp": 10, "items": []}
    }

    # First validate and save it to history
    valid, _ = QuestValidationEngine.validate_quest(db, quest_payload)
    assert valid is True

    # Persist in DB so duplicate scan detects it
    db_quest = GeneratedQuest(
        id=uuid.uuid4(),
        npc_slug="eldrin",
        title=quest_payload["title"],
        objectives=quest_payload["objectives"],
        rewards=quest_payload["rewards"],
        difficulty=quest_payload["difficulty"]
    )
    db.add(db_quest)
    db.commit()

    # Invalidate validation cache by incrementing NPC stamp
    graph_cache.increment_entity_stamp("eldrin")

    # Try validating again (should detect duplicate title)
    valid_second, reasons = QuestValidationEngine.validate_quest(db, quest_payload)

    assert valid_second is False
    assert any("Duplicate quest found" in r for r in reasons)

    # Telemetry should register duplicate rejection
    logs = db.query(LLMTelemetryLog).filter(LLMTelemetryLog.action_type == "quest_duplicate_rejections_total").all()
    assert len(logs) >= 1


# ----------------------------------------------------
# Gate E: Reward Balancing
# ----------------------------------------------------
def test_gate_e_reward_balancing():
    # If total rewards > 5, we clamp items.
    scaling_config = {
        "gold_multiplier": 10,
        "xp_multiplier": 30,
        "base_items": ["item1", "item2", "item3", "item4", "item5"]
    }
    rewards, adjusted = QuestTemplateEngine.scale_rewards(
        player_level=10,
        difficulty="Medium",
        reward_scaling=scaling_config
    )
    assert adjusted is True
    # Gold and XP take 2 slots, so max items is 3
    assert len(rewards["items"]) == 3
    assert rewards["gold"] > 0
    assert rewards["xp"] > 0


# ----------------------------------------------------
# Gate F: Faction / World State Validation
# ----------------------------------------------------
def test_gate_f_faction_world_state_validation(db):
    # Validate quest with non-existing NPC
    quest_payload = {
        "npc_slug": "non_existent_npc",
        "title": "Clean the Void",
        "description": "Defeat void monsters",
        "difficulty": "Hard",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Defeat the monsters",
                "target_type": "kill",
                "target_id": "void_monster",
                "quantity_required": 5
            }
        ],
        "rewards": {"gold": 50, "xp": 50, "items": []}
    }
    valid, reasons = QuestValidationEngine.validate_quest(db, quest_payload)
    assert valid is False
    assert any("does not exist" in r for r in reasons)


# ----------------------------------------------------
# Gate G: Telemetry Persistence
# ----------------------------------------------------
def test_gate_g_telemetry_persistence(db):
    setup_npc_helper(db, name="Eldrin", slug="eldrin")
    db.query(LLMTelemetryLog).delete()
    db.commit()

    # Trigger generation which writes telemetry
    DynamicQuestGenerator.generate_quest(
        db=db,
        npc_slug="eldrin",
        player_id="player_telemetry",
        player_level=10
    )

    # Verify metrics logged
    generated_log = db.query(LLMTelemetryLog).filter(
        LLMTelemetryLog.action_type == "dynamic_quests_generated_total"
    ).first()
    assert generated_log is not None

    duration_log = db.query(LLMTelemetryLog).filter(
        LLMTelemetryLog.action_type == "dynamic_quest_generation_duration_seconds"
    ).first()
    assert duration_log is not None


# ----------------------------------------------------
# Gate H: Cache Coherence
# ----------------------------------------------------
def test_gate_h_cache_coherence(db):
    setup_npc_helper(db, name="Eldrin", slug="eldrin")
    # Verify cached quest retrieval works on same parameters
    npc_slug = "eldrin"
    player_id = "player_cache"

    # Make sure cache is clean
    redis_client = graph_cache.redis
    redis_client.set(f"graph:version:entity:{npc_slug}", b"1")

    # Generate first time (cache miss)
    q1 = DynamicQuestGenerator.generate_quest(db, npc_slug, player_id, 10)

    # Generate second time (should hit cache)
    q2 = DynamicQuestGenerator.generate_quest(db, npc_slug, player_id, 10)
    assert q1["title"] == q2["title"]

    # Invalidate cache by incrementing stamp
    graph_cache.increment_entity_stamp(npc_slug)

    # Check cache retrieval directly (should miss now)
    cached, hit = DynamicQuestGenerator.get_cached_quest(npc_slug, player_id)
    assert hit is False


# ----------------------------------------------------
# Gate I: API Validation
# ----------------------------------------------------
def test_gate_i_api_validation(db):
    setup_npc_helper(db, name="Eldrin", slug="eldrin")
    # Test GET templates
    res = client.get("/api/v1/quests/templates")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Test POST generate with non-existent NPC (should return 422)
    payload_invalid = {
        "npc_slug": "invalid_slug",
        "player_id": "player1",
        "player_level": 5
    }
    res = client.post("/api/v1/quests/generate", json=payload_invalid)
    assert res.status_code == 422

    # Test POST generate with valid NPC (should return 200)
    payload_valid = {
        "npc_slug": "eldrin",
        "player_id": "player1",
        "player_level": 5
    }
    res = client.post("/api/v1/quests/generate", json=payload_valid)
    assert res.status_code == 200
    assert "title" in res.json()

    # Test POST validate bounds checks (objectives > 10 should return 422)
    validate_payload = {
        "npc_slug": "eldrin",
        "title": "Overlimit Objectives",
        "objectives": [{"objective_index": i, "description": f"D{i}", "target_type": "speak", "target_id": "N", "quantity_required": 1} for i in range(11)],
        "rewards": {"gold": 10}
    }
    res = client.post("/api/v1/quests/validate", json=validate_payload)
    assert res.status_code == 422

    # Test GET generated
    res = client.get("/api/v1/quests/generated?npc_slug=eldrin")
    assert res.status_code == 200
    assert len(res.json()) >= 1

