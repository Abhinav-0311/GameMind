import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective, QuestProgress
from app.models.memory import NPCMemory
from sqlalchemy import text
import uuid
import datetime

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        # Clear tables
        db_session.query(QuestProgress).delete()
        db_session.query(QuestObjective).delete()
        db_session.query(Quest).delete()
        db_session.commit()
        yield db_session
    finally:
        db_session.query(QuestProgress).delete()
        db_session.query(QuestObjective).delete()
        db_session.query(Quest).delete()
        db_session.commit()
        db_session.close()

@pytest.fixture(scope="module")
def test_npc(db):
    npc_slug = f"quest_npc_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Quest Giver Eldrin",
        personality_summary="Gives puzzle quests.",
        dialogue_style="Polite and helpful.",
        voice_profile="soft",
        faction_alignment="mages"
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)
    yield npc
    db.delete(npc)
    db.commit()

def test_quest_registration(db, test_npc):
    payload = {
        "npc_slug": test_npc.slug,
        "title": "Restoring the Heat",
        "description": "Collect magma cores to heat the watchtower.",
        "difficulty": "Easy",
        "gold_reward": 50,
        "xp_reward": 200,
        "item_rewards": ["magma_core_item"],
        "objectives": [
            {
                "objective_index": 0,
                "description": "Defeat 2 lava slimes",
                "target_type": "kill",
                "target_id": "lava_slime",
                "quantity_required": 2
            },
            {
                "objective_index": 1,
                "description": "Speak to Ignis",
                "target_type": "speak",
                "target_id": "ignis",
                "quantity_required": 1
            }
        ]
    }
    res = client.post("/api/v1/quests", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Restoring the Heat"
    assert len(data["objectives"]) == 2
    assert data["objectives"][0]["objective_index"] == 0
    assert data["objectives"][0]["quantity_required"] == 2

    # Verify directly in DB
    q = db.query(Quest).filter(Quest.id == data["id"]).first()
    assert q is not None
    assert q.npc_slug == test_npc.slug

def test_quest_acceptance(db, test_npc):
    # Register quest first
    q_payload = {
        "npc_slug": test_npc.slug,
        "title": "Watchtower Defenses",
        "description": "Set up barricades.",
        "difficulty": "Medium",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Gather 3 wood",
                "target_type": "retrieve",
                "target_id": "wood",
                "quantity_required": 3
            }
        ]
    }
    q_res = client.post("/api/v1/quests", json=q_payload)
    assert q_res.status_code == 201
    q_data = q_res.json()

    # Accept quest
    progress_payload = {
        "player_id": "test_player_a",
        "quest_id": q_data["id"]
    }
    res = client.post("/api/v1/quests/progress", json=progress_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["player_id"] == "test_player_a"
    assert data["status"] == "active"
    assert data["objectives_state"] == {"0": 0}

def test_objective_progression_and_completion_memory(db, test_npc):
    # Register quest with 1 objective
    q_payload = {
        "npc_slug": test_npc.slug,
        "title": "Eldrin's Valve",
        "description": "Repair the steam valve.",
        "difficulty": "Medium",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Retrieve 1 steel valve",
                "target_type": "retrieve",
                "target_id": "steel_valve",
                "quantity_required": 1
            }
        ]
    }
    q_res = client.post("/api/v1/quests", json=q_payload)
    assert q_res.status_code == 201
    q_data = q_res.json()
    quest_id = q_data["id"]

    # Accept quest
    client.post("/api/v1/quests/progress", json={
        "player_id": "test_player_b",
        "quest_id": quest_id
    })

    # Update progress to completion
    update_payload = {
        "player_id": "test_player_b",
        "quest_id": quest_id,
        "objective_index": 0,
        "increment_amount": 1
    }
    res = client.post("/api/v1/quests/progress/update", json=update_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None
    assert data["objectives_state"] == {"0": 1}

    # Verify episodic memory was written to DB with metadata
    db.expire_all()
    mem = db.query(NPCMemory).filter(
        NPCMemory.npc_id == test_npc.id,
        NPCMemory.memory_type == "episodic"
    ).order_by(NPCMemory.created_at.desc()).first()

    assert mem is not None
    assert "Eldrin's Valve" in mem.memory_text
    assert mem.metadata_json is not None
    assert mem.metadata_json["type"] == "quest_completion"
    assert mem.metadata_json["quest_id"] == quest_id
    assert mem.metadata_json["quest_title"] == "Eldrin's Valve"
    assert mem.metadata_json["npc_slug"] == test_npc.slug

def test_dialogue_prompt_injection(db, test_npc):
    # Setup active and completed quests for default_player
    # Active Quest
    active_q = client.post("/api/v1/quests", json={
        "npc_slug": test_npc.slug,
        "title": "Active Quest Dial",
        "description": "Active dial description",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Find 2 gears",
                "target_type": "retrieve",
                "target_id": "gear",
                "quantity_required": 2
            }
        ]
    }).json()

    # 3 Completed Quests (limit 3 DESC check)
    completed_qs = []
    for i in range(4):
        q = client.post("/api/v1/quests", json={
            "npc_slug": test_npc.slug,
            "title": f"Comp Quest {i}",
            "description": "Completed",
            "objectives": [
                {
                    "objective_index": 0,
                    "description": "Talk",
                    "target_type": "speak",
                    "target_id": "giver",
                    "quantity_required": 1
                }
            ]
        }).json()
        completed_qs.append(q)

    # Accept all
    client.post("/api/v1/quests/progress", json={"player_id": "default_player", "quest_id": active_q["id"]})
    for q in completed_qs:
        client.post("/api/v1/quests/progress", json={"player_id": "default_player", "quest_id": q["id"]})
        # Complete them
        client.post("/api/v1/quests/progress/update", json={
            "player_id": "default_player",
            "quest_id": q["id"],
            "objective_index": 0,
            "increment_amount": 1
        })

    # Update one objective on active quest
    client.post("/api/v1/quests/progress/update", json={
        "player_id": "default_player",
        "quest_id": active_q["id"],
        "objective_index": 0,
        "increment_amount": 1
    })

    # Call assemble endpoint
    res = client.post("/api/v1/dialogue/assemble", json={
        "npc_slug": test_npc.slug,
        "player_message": "How are my quests coming?",
        "selected_chunk_ids": [],
        "player_id": "default_player"
    })
    assert res.status_code == 200
    data = res.json()
    assembled = data["assembled_prompt"]

    assert "[NPC Quests]" in assembled
    assert "Active: Active Quest Dial (Find 2 gears: 1/2)" in assembled
    
    # Verify latest 3 completed quests are shown
    # Latest 3 should be Comp Quest 3, Comp Quest 2, Comp Quest 1 (Comp Quest 0 is oldest and should be left out)
    assert "Completed: Comp Quest 3" in assembled
    assert "Completed: Comp Quest 2" in assembled
    assert "Completed: Comp Quest 1" in assembled
    assert "Completed: Comp Quest 0" not in assembled
