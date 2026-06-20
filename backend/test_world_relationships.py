import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.relationship import NPCRelationship
from app.models.world_state import WorldStateFlag
from app.services.dialogue_service import DialogueService
from sqlalchemy.exc import IntegrityError
import uuid
import time

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        # Clear existing world state and relationships to start fresh
        db_session.query(WorldStateFlag).delete()
        db_session.query(NPCRelationship).delete()
        db_session.commit()
        yield db_session
    finally:
        db_session.close()

@pytest.fixture(scope="module")
def test_npc(db):
    npc_slug = f"world_npc_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Oracle of Wind",
        personality_summary="An oracle representing forces.",
        dialogue_style="Enigmatic.",
        voice_profile="soft",
        faction_alignment="oracles"
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)
    return npc

def test_relationship_creation_and_unique_constraint(db, test_npc):
    # 1. Update relationship via API (Create scenario)
    payload = {
        "npc_slug": test_npc.slug,
        "player_id": "test_player_1",
        "trust": 75,
        "respect": 65,
        "friendship": 50,
        "fear": 10,
        "last_reason": "Player solved the first puzzle."
    }
    res = client.post("/api/v1/relationships/update", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["npc_slug"] == test_npc.slug
    assert data["player_id"] == "test_player_1"
    assert data["trust"] == 75
    assert data["standing"] == "Trusted Ally"
    assert data["last_reason"] == "Player solved the first puzzle."

    # 2. Database unique constraint check (duplicate player_id + npc_slug)
    db.rollback()
    dup_rel = NPCRelationship(
        id=uuid.uuid4(),
        player_id="test_player_1",
        npc_slug=test_npc.slug,
        trust=40
    )
    db.add(dup_rel)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_relationship_updates_and_last_reason_persistence(db, test_npc):
    # 1. Update existing standing via API
    payload = {
        "npc_slug": test_npc.slug,
        "player_id": "test_player_1",
        "trust": 90,
        "respect": 80,
        "friendship": 50,
        "fear": 5,
        "last_reason": "Player saved the Oracle from the void."
    }
    res = client.post("/api/v1/relationships/update", json=payload)
    assert res.status_code == 200
    
    # Check directly in DB
    db.expire_all()
    rel = db.query(NPCRelationship).filter(
        NPCRelationship.npc_slug == test_npc.slug,
        NPCRelationship.player_id == "test_player_1"
    ).first()
    assert rel is not None
    assert rel.trust == 90
    assert rel.respect == 80
    assert rel.last_reason == "Player saved the Oracle from the void."

def test_standing_label_mapping():
    # Helper semantic mappings check
    assert DialogueService.get_standing_label(trust=50, respect=50, friendship=50, fear=60) == "Feared Figure"
    assert DialogueService.get_standing_label(trust=70, respect=60, friendship=50, fear=0) == "Trusted Ally"
    assert DialogueService.get_standing_label(trust=50, respect=50, friendship=75, fear=10) == "Close Friend"
    assert DialogueService.get_standing_label(trust=50, respect=80, friendship=50, fear=0) == "Respected Hero"
    assert DialogueService.get_standing_label(trust=20, respect=50, friendship=50, fear=0) == "Distrusted"
    assert DialogueService.get_standing_label(trust=50, respect=50, friendship=50, fear=0) == "Neutral"

def test_world_state_creation_and_priority_ordering(db):
    # Explicit status updates
    payload1 = {
        "flag_key": "siege_active",
        "flag_value": "The Ember Siege is active.",
        "is_active": True,
        "priority": 5
    }
    payload2 = {
        "flag_key": "storm_active",
        "flag_value": "A violent lightning storm has rolled in.",
        "is_active": True,
        "priority": 15
    }
    payload3 = {
        "flag_key": "festival_active",
        "flag_value": "The Spring Festival has started.",
        "is_active": True,
        "priority": 1
    }

    # Post via API
    assert client.post("/api/v1/world-state/toggle", json=payload1).status_code == 200
    assert client.post("/api/v1/world-state/toggle", json=payload2).status_code == 200
    assert client.post("/api/v1/world-state/toggle", json=payload3).status_code == 200

    # Retrieve all flags, check order (storm priority 15, siege priority 5, festival priority 1)
    res = client.get("/api/v1/world-state")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3
    assert data[0]["flag_key"] == "storm_active"
    assert data[1]["flag_key"] == "siege_active"
    assert data[2]["flag_key"] == "festival_active"

def test_dialogue_prompt_injection(db, test_npc):
    # Initialize a relationship for the 'default_player' player_id to inject in prompt
    payload = {
        "npc_slug": test_npc.slug,
        "player_id": "default_player",
        "trust": 85,
        "respect": 70,
        "friendship": 50,
        "fear": 0,
        "last_reason": "Oracle appreciates player's dedication."
    }
    client.post("/api/v1/relationships/update", json=payload)

    # Trigger dialogue prompt assembly
    payload_assemble = {
        "npc_slug": test_npc.slug,
        "player_message": "What is the status of the world?",
        "selected_chunk_ids": []
    }
    res = client.post("/api/v1/dialogue/assemble", json=payload_assemble)
    assert res.status_code == 200
    data = res.json()
    assembled = data["assembled_prompt"]

    # Verify NPC Relationship section
    assert "[NPC Relationship]" in assembled
    assert "Standing: Trusted Ally" in assembled
    assert "Trust: 85/100" in assembled
    assert "Last Update Reason: Oracle appreciates player's dedication." in assembled

    # Verify World State Context priority ordered section
    assert "[World State Context]" in assembled
    storm_idx = assembled.index("storm_active: A violent lightning storm has rolled in.")
    siege_idx = assembled.index("siege_active: The Ember Siege is active.")
    fest_idx = assembled.index("festival_active: The Spring Festival has started.")
    assert storm_idx < siege_idx < fest_idx
