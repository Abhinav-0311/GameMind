import pytest
import uuid
import datetime
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.relationship import NPCRelationship
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.models.world_state import WorldStateFlag
from app.models.session import Conversation, Message
from app.models.telemetry import LLMTelemetryLog
from app.schemas import DialogueAssembleRequest, EmotionUpdateRequest

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        # Clear tables
        session.query(Message).delete()
        session.query(Conversation).delete()
        session.query(NPCRelationship).delete()
        session.query(WorldRelationship).delete()
        session.query(WorldEntityVersion).delete()
        session.query(WorldEntity).delete()
        session.query(WorldStateFlag).delete()
        session.query(NPCProfile).delete()
        session.query(LLMTelemetryLog).delete()
        session.commit()
        yield session
    finally:
        session.query(Message).delete()
        session.query(Conversation).delete()
        session.query(NPCRelationship).delete()
        session.query(WorldRelationship).delete()
        session.query(WorldEntityVersion).delete()
        session.query(WorldEntity).delete()
        session.query(WorldStateFlag).delete()
        session.query(NPCProfile).delete()
        session.query(LLMTelemetryLog).delete()
        session.commit()
        session.close()

# ----------------------------------------------------
# Gate A: Personality Engine default and custom verification
# ----------------------------------------------------
def test_gate_a_personality_engine(db):
    from app.services.personality_engine import PersonalityEngine

    # 1. Defaults
    defaults = PersonalityEngine.get_defaults()
    assert defaults["traits"]["courage"] == 50
    assert defaults["relationship_modifiers"]["trust_gain_multiplier"] == 1.0

    # 2. Custom metadata parsing
    npc = NPCProfile(
        id=uuid.uuid4(),
        slug="galahad",
        name="Sir Galahad",
        personality_summary="A brave and loyal knight",
        metadata_json={
            "personality": {
                "traits": {
                    "courage": 95,
                    "sociability": 30
                },
                "relationship_modifiers": {
                    "trust_gain_multiplier": 1.5
                }
            }
        }
    )
    db.add(npc)
    db.commit()

    eval_res = PersonalityEngine.evaluate_personality(db, "galahad")
    assert eval_res["traits"]["courage"] == 95
    assert eval_res["traits"]["sociability"] == 30
    assert eval_res["traits"]["intelligence"] == 50 # Merged default
    assert eval_res["relationship_modifiers"]["trust_gain_multiplier"] == 1.5

# ----------------------------------------------------
# Gate B: Emotional state transitions & boundary checks
# ----------------------------------------------------
def test_gate_b_emotion_engine(db):
    from app.services.emotion_engine import EmotionEngine

    # Defaults check
    emotions = EmotionEngine.get_emotional_state(db, "galahad", "player1")
    assert emotions["trust"] == 50
    assert emotions["fear"] == 0
    assert emotions["anger"] == 0
    assert emotions["curiosity"] == 0
    assert emotions["loyalty"] == 0

    # Updates and serialization
    updates = {
        "trust": 80,
        "anger": 20,
        "loyalty": 75
    }
    updated = EmotionEngine.update_emotional_state(db, "galahad", "player1", updates, reason="Helped the village")
    assert updated["trust"] == 80
    assert updated["anger"] == 20
    assert updated["loyalty"] == 75

    # Check persistence
    rel = db.query(NPCRelationship).filter_by(npc_slug="galahad", player_id="player1").first()
    assert rel is not None
    assert rel.trust == 80
    assert rel.last_reason == "Helped the village"

    flag = db.query(WorldStateFlag).filter_by(flag_key="emotion:galahad:player1").first()
    assert flag is not None
    assert "anger" in flag.flag_value
    assert "loyalty" in flag.flag_value

    # Bounds check
    with pytest.raises(ValueError):
        EmotionEngine.update_emotional_state(db, "galahad", "player1", {"trust": 150}) # > 100

    with pytest.raises(ValueError):
        EmotionEngine.update_emotional_state(db, "galahad", "player1", {"anger": -5}) # < 0

# ----------------------------------------------------
# Gate C: Conversation goal & topic priority generation
# ----------------------------------------------------
def test_gate_c_conversation_planner(db):
    # Setup graph nodes
    npc_ent = WorldEntity(id=uuid.uuid4(), slug="galahad", entity_type="npc")
    item_ent = WorldEntity(id=uuid.uuid4(), slug="grail", entity_type="item")
    db.add_all([npc_ent, item_ent])
    db.commit()

    db.add_all([
        WorldEntityVersion(entity_id=npc_ent.id, version=1, name="Sir Galahad", description=""),
        WorldEntityVersion(entity_id=item_ent.id, version=1, name="Holy Grail", description="")
    ])
    db.commit()

    # Relationship edge in graph
    rel = WorldRelationship(
        source_id=npc_ent.id,
        target_id=item_ent.id,
        rel_type="seeking",
        version=1
    )
    db.add(rel)
    db.commit()

    from app.services.conversation_planner import ConversationPlanner
    plan = ConversationPlanner.generate_plan(db, "galahad", "player1", "Tell me about the grail")
    
    assert len(plan["topic_priorities"]) > 0
    # The topic "Holy Grail" (slug "grail") should have priority 10 because "grail" is in player message
    grail_topic = next((t for t in plan["topic_priorities"] if t["slug"] == "grail"), None)
    assert grail_topic is not None
    assert grail_topic["priority"] == 10

    # Goals limit
    assert len(plan["goals"]) <= 5

# ----------------------------------------------------
# Gate D: Dialogue style directives compilation
# ----------------------------------------------------
def test_gate_d_dialogue_style_engine():
    from app.services.dialogue_style_engine import DialogueStyleEngine

    personality = {
        "traits": {
            "courage": 85,
            "sociability": 20, # low sociability -> cold/brief
            "intelligence": 50,
            "temperament": 50
        }
    }
    emotions = {
        "trust": 80,
        "fear": 0,
        "anger": 70, # high anger -> hostile/sharp
        "curiosity": 0,
        "loyalty": 0
    }

    directives = DialogueStyleEngine.get_directives(personality, emotions)
    assert len(directives) <= 8
    # Should include low sociability directive or high anger directive
    assert any("cold" in d or "brief" in d for d in directives)
    assert any("hostile" in d or "sharp" in d or "accusatory" in d for d in directives)

# ----------------------------------------------------
# Gate E: Conversation continuity keyword hits/misses
# ----------------------------------------------------
def test_gate_e_conversation_continuity(db):
    # Setup conversation and messages
    npc = db.query(NPCProfile).filter_by(slug="galahad").first()
    conv = Conversation(id=uuid.uuid4(), npc_id=npc.id, npc_slug=npc.slug)
    db.add(conv)
    db.commit()

    msg1 = Message(conversation_id=conv.id, sender="player", content="Have you seen Arthur?")
    msg2 = Message(conversation_id=conv.id, sender="npc", content="I heard King Arthur is in Camelot.")
    db.add_all([msg1, msg2])
    db.commit()

    from app.services.conversation_continuity import ConversationContinuity
    
    # 1. Hit verification
    res = ConversationContinuity.analyze_continuity(db, conv.id, "Arthur and Camelot are famous")
    assert "Arthur" in res["hits"]
    assert "Camelot" in res["hits"]
    assert res["continuity_score"] > 0.0

    # 2. Miss verification
    res_miss = ConversationContinuity.analyze_continuity(db, conv.id, "Where is Merlin?")
    assert "Merlin" in res_miss["misses"]
    assert len(res_miss["hits"]) == 0

    # Limits verification (keywords <= 20)
    long_msg = " ".join([f"Word{i}" for i in range(30)])
    res_limit = ConversationContinuity.analyze_continuity(db, conv.id, long_msg)
    assert len(res_limit["keywords"]) <= 20

# ----------------------------------------------------
# Gate F: Telemetry persistence verification
# ----------------------------------------------------
def test_gate_f_telemetry_persistence(db):
    # Trigger all telemetry generation events to ensure they exist
    from app.services.personality_engine import PersonalityEngine
    from app.services.emotion_engine import EmotionEngine
    from app.services.conversation_planner import ConversationPlanner
    from app.services.conversation_continuity import ConversationContinuity
    from app.services.dialogue_service import DialogueService
    from app.schemas import DialogueAssembleRequest
    
    # 1. Personality evaluation
    PersonalityEngine.evaluate_personality(db, "galahad")
    # 2. Emotion read & update
    EmotionEngine.get_emotional_state(db, "galahad", "player1")
    EmotionEngine.update_emotional_state(db, "galahad", "player1", {"trust": 50})
    # 3. Conversation plan
    ConversationPlanner.generate_plan(db, "galahad", "player1", "hello")
    # 4. Conversation continuity
    ConversationContinuity.analyze_continuity(db, uuid.uuid4(), "hello")
    # 5. Assemble prompt (triggers style directives and prompt sections telemetry)
    DialogueService.assemble_prompt(db, DialogueAssembleRequest(npc_slug="galahad", player_message="hello"))
    
    metrics = [
        "personality_profile_evaluations_total",
        "emotion_state_reads_total",
        "emotional_state_updates_total",
        "conversation_plans_generated_total",
        "conversation_continuity_evaluations_total",
        "dialogue_style_directives_generated_total",
        "dialogue_prompt_sections_generated_total",
        "dialogue_assembly_duration_seconds",
        "dialogue_assembled_tokens_total",
        "dialogue_history_messages_scanned_total"
    ]
    for metric in metrics:
        logs = db.query(LLMTelemetryLog).filter(LLMTelemetryLog.action_type == metric).all()
        assert len(logs) > 0


# ----------------------------------------------------
# Gate G: Narrative consistency validation compatibility
# ----------------------------------------------------
def test_gate_g_consistency_validation(db):
    # Register relationship for consistency check
    npc_ent = db.query(WorldEntity).filter_by(slug="galahad").first()
    item_ent = db.query(WorldEntity).filter_by(slug="grail").first()
    
    # Check narrative verify endpoint using claims model
    payload = {
        "claims": [
            {
                "subject": "galahad",
                "predicate": "seeking",
                "object": "grail"
            }
        ]
    }
    res = client.post("/api/v1/narrative/verify", json=payload)
    assert res.status_code == 200
    assert res.json()["consistent"] is True

# ----------------------------------------------------
# Gate I: Prompt Assembly Stability & Token Budget
# ----------------------------------------------------
def test_gate_i_prompt_assembly_stability(db):
    npc = db.query(NPCProfile).filter_by(slug="galahad").first()
    conv = db.query(Conversation).filter_by(npc_slug="galahad").first()

    payload = {
        "npc_slug": "galahad",
        "player_message": "Can you tell me about the Grail?",
        "player_id": "player1",
        "conversation_id": str(conv.id)
    }

    res = client.post("/api/v1/dialogue/assemble", json=payload)
    assert res.status_code == 200
    data = res.json()
    
    assert data["npc_slug"] == "galahad"
    assert "[NPC Personality & Traits]" in data["assembled_prompt"]
    assert "[NPC Emotion State]" in data["assembled_prompt"]
    assert "[NPC Conversation Plan]" in data["assembled_prompt"]
    assert "[Dialogue Directives]" in data["assembled_prompt"]
    assert "[Conversation Continuity]" in data["assembled_prompt"]
    
    # Budget check
    assert data["estimated_tokens"] <= 1024 + 100  # allowing slight safety margin for defaults

# ----------------------------------------------------
# Gate J: API Endpoints (GET and POST /emotion)
# ----------------------------------------------------
def test_gate_j_api_endpoints(db):
    # GET /api/v1/narrative/emotion
    res = client.get("/api/v1/narrative/emotion", params={"npc_slug": "galahad", "player_id": "player1"})
    assert res.status_code == 200
    data = res.json()
    assert data["npc_slug"] == "galahad"
    assert data["player_id"] == "player1"
    assert "trust" in data["emotions"]

    # POST /api/v1/narrative/emotion
    payload = {
        "npc_slug": "galahad",
        "player_id": "player1",
        "updates": {
            "trust": 90,
            "fear": 10,
            "anger": 5
        },
        "reason": "Gift accepted"
    }
    res = client.post("/api/v1/narrative/emotion", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["emotions"]["trust"] == 90
    assert data["emotions"]["fear"] == 10
    assert data["emotions"]["anger"] == 5

    # 422 boundary validation
    payload_bad = {
        "npc_slug": "galahad",
        "player_id": "player1",
        "updates": {
            "trust": 150
        }
    }
    res = client.post("/api/v1/narrative/emotion", json=payload_bad)
    assert res.status_code == 422
