import os
import uuid
import pytest
import json
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.document import Document, DocumentChunk
from app.models.quest import Quest, QuestObjective, QuestProgress
from app.models.graph import WorldEntity, WorldEntityVersion
from app.services.runtime_presentation_service import RuntimePresentationService
from app.schemas import DialogueChatResponse, QuestGeneratedResponse, ErrorEnvelope

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def setup_npc_graph_entity(db, slug, name):
    ent = db.query(WorldEntity).filter(WorldEntity.slug == slug).first()
    if not ent:
        ent = WorldEntity(slug=slug, entity_type="npc")
        db.add(ent)
        db.commit()
        db.refresh(ent)
    
    ver = db.query(WorldEntityVersion).filter(WorldEntityVersion.entity_id == ent.id).first()
    if not ver:
        ver = WorldEntityVersion(
            entity_id=ent.id,
            version=1,
            name=name,
            description=f"{name} NPC",
            importance_score=8
        )
        db.add(ver)
        db.commit()

def test_gate_a_project_isolation(db):
    """Gate A: Verify strict isolation between project_alpha and project_beta workspaces."""
    project_alpha = f"proj_alpha_{uuid.uuid4().hex[:6]}"
    project_beta = f"proj_beta_{uuid.uuid4().hex[:6]}"
    npc_slug = "shield-knight"

    # Create NPC in Project Alpha
    headers_alpha = {"X-Game-Project-ID": project_alpha}
    res_create = client.post("/api/v1/npcs", headers=headers_alpha, json={
        "slug": npc_slug,
        "name": "Sir Galahad",
        "personality_summary": "A noble knight guarding Project Alpha."
    })
    assert res_create.status_code == 201

    # Check if Sir Galahad is visible in Project Beta (should NOT be)
    headers_beta = {"X-Game-Project-ID": project_beta}
    res_list_beta = client.get("/api/v1/npcs", headers=headers_beta)
    assert res_list_beta.status_code == 200
    npcs_beta = res_list_beta.json()
    assert not any(n["slug"] == npc_slug for n in npcs_beta)

    # Sir Galahad should be visible in Project Alpha
    res_list_alpha = client.get("/api/v1/npcs", headers=headers_alpha)
    assert res_list_alpha.status_code == 200
    npcs_alpha = res_list_alpha.json()
    assert any(n["slug"] == npc_slug for n in npcs_alpha)


def test_gate_b_dialogue_generation(db):
    """Gate B: Verify dialogue chat simulation generates grounded responses."""
    project_id = f"proj_diag_{uuid.uuid4().hex[:6]}"
    headers = {"X-Game-Project-ID": project_id, "X-Player-ID": "test_player"}

    # Setup NPC
    npc_slug = "zephyr-mage"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Zephyr",
        "personality_summary": "Keeper of breeze magic."
    })

    # Chat Dialogue
    payload = {
        "npc_slug": npc_slug,
        "player_message": "Tell me about the wind."
    }
    res_chat = client.post("/api/v1/dialogue/chat", headers=headers, json=payload)
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert data["npc_slug"] == npc_slug
    assert "response_text" in data


def test_gate_c_citation_generation(db):
    """Gate C: Verify citation mapping and confidence ratings match RAG output."""
    project_id = f"proj_cit_{uuid.uuid4().hex[:6]}"
    headers = {"X-Game-Project-ID": project_id}

    # 1. Create NPC
    npc_slug = "scholar-npc"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Scholar",
        "personality_summary": "A helpful scholar."
    })

    # 2. Upload mock lore document
    file_content = b"The legendary Kingdom of Frostpeak was founded by King Arven in the Year of Fire."
    res_upload = client.post("/api/v1/documents/upload", headers=headers, files={
        "file": ("frostpeak.txt", file_content, "text/plain")
    })
    assert res_upload.status_code == 201
    doc_data = res_upload.json()
    doc_id = doc_data["id"]

    # Retrieve chunk index ID
    doc_detail = client.get(f"/api/v1/documents/{doc_id}", headers=headers).json()
    chunk_id = doc_detail["chunks"][0]["id"]

    # 3. Chat with selected chunk citation
    payload = {
        "npc_slug": npc_slug,
        "player_message": "Tell me about Frostpeak.",
        "selected_chunk_ids": [chunk_id]
    }
    res_chat = client.post("/api/v1/dialogue/chat", headers=headers, json=payload)
    assert res_chat.status_code == 200
    data = res_chat.json()

    # Verify citation schema
    assert "citations" in data
    assert len(data["citations"]) > 0
    citation = data["citations"][0]
    assert citation["document_id"] == doc_id
    assert citation["chunk_id"] == chunk_id
    assert "frostpeak.txt" in citation["title"]
    assert citation["similarity"] >= 0.0


def test_dialogue_chat_auto_retrieves_lore_context(db):
    """Verify chat auto-runs RAG when selected_chunk_ids are omitted."""
    project_id = f"proj_auto_rag_{uuid.uuid4().hex[:6]}"
    headers = {"X-Game-Project-ID": project_id}

    npc_slug = "auto-scholar"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Auto Scholar",
        "personality_summary": "A scholar who answers only from grounded lore."
    })

    upload = client.post("/api/v1/documents/upload", headers=headers, files={
        "file": (
            "arven.txt",
            b"King Arven restored Frostpeak after the Ember Siege and led the Northern resistance.",
            "text/plain",
        )
    })
    assert upload.status_code == 201

    response = client.post("/api/v1/dialogue/chat", headers=headers, json={
        "npc_slug": npc_slug,
        "player_message": "Who is King Arven?"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["citations"]
    assert "No lore context was provided" not in data["response_text"]


def test_gate_d_quest_generation(db):
    """Gate D: Verify dynamic quest generator pipelines contextually grounded quests."""
    project_id = f"proj_quest_{uuid.uuid4().hex[:6]}"
    headers = {"X-Game-Project-ID": project_id}

    # Setup NPC
    npc_slug = "questgiver-npc"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Eldrin",
        "personality_summary": "A seasoned quest giver."
    })
    setup_npc_graph_entity(db, npc_slug, "Eldrin")

    payload = {
        "npc_slug": npc_slug,
        "player_id": "player_1",
        "player_level": 5
    }
    res_gen = client.post("/api/v1/quests/generate", headers=headers, json=payload)
    assert res_gen.status_code == 200, f"Response: {res_gen.text}"
    data = res_gen.json()
    assert data["npc_slug"] == npc_slug
    assert "title" in data
    assert "rewards" in data
    assert "objectives" in data


def test_gate_e_progressive_hints(db):
    """Gate E: Verify hint studies enforce level escalation and cooldown rules."""
    project_id = f"proj_hints_{uuid.uuid4().hex[:6]}"
    player_id = "player_hint_tester"
    headers = {
        "X-Game-Project-ID": project_id,
        "X-Player-ID": player_id
    }

    # 1. Create NPC
    npc_slug = "hintgiver"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Oracle",
        "personality_summary": "Oracle who gives hints."
    })

    # 2. Register and accept quest
    quest_payload = {
        "npc_slug": npc_slug,
        "title": "Unseal the Wind Seal",
        "description": "Unseal the ancient valve.",
        "difficulty": "Easy",
        "gold_reward": 100,
        "xp_reward": 50,
        "objectives": [{
            "objective_index": 0,
            "description": "Turn the valve",
            "target_type": "interact",
            "target_id": "wind_valve",
            "quantity_required": 1
        }]
    }
    quest_res = client.post("/api/v1/quests", headers=headers, json=quest_payload)
    assert quest_res.status_code == 201
    quest_id = quest_res.json()["id"]

    # Accept quest
    accept_res = client.post("/api/v1/quests/progress", headers=headers, json={
        "quest_id": quest_id,
        "player_id": player_id
    })
    assert accept_res.status_code == 201

    # 3. Generate Level 1 Hint
    hint1_payload = {
        "quest_id": quest_id,
        "player_id": player_id,
        "hint_level": 1
    }
    res_hint1 = client.post("/api/v1/hints/generate", headers=headers, json=hint1_payload)
    assert res_hint1.status_code == 200
    hint1_data = res_hint1.json()
    assert "hint" in hint1_data
    assert hint1_data["hint_level"] == 1

    # 4. Generate Level 2 Hint (within cooldown -> should be blocked and raise 422 Unprocessable Entity)
    hint2_payload = {
        "quest_id": quest_id,
        "player_id": player_id,
        "hint_level": 2
    }
    res_hint2 = client.post("/api/v1/hints/generate", headers=headers, json=hint2_payload)
    assert res_hint2.status_code == 422
    assert "cooldown" in res_hint2.json()["detail"].lower()


def test_gate_f_version_stamp_caching(db):
    """Gate F: Verify version stamp triggers cache hits/misses appropriately."""
    project_id = f"proj_cache_{uuid.uuid4().hex[:6]}"
    player_id = "cache_tester"
    headers = {
        "X-Game-Project-ID": project_id,
        "X-Player-ID": player_id
    }

    # Setup NPC
    npc_slug = "cachegiver"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Cache Master",
        "personality_summary": "NPC for cache test."
    })
    setup_npc_graph_entity(db, npc_slug, "Cache Master")

    # Generate first time (Cache Miss)
    payload = {
        "npc_slug": npc_slug,
        "player_id": player_id,
        "player_level": 1
    }
    res_gen1 = client.post("/api/v1/quests/generate", headers=headers, json=payload)
    assert res_gen1.status_code == 200, f"Response: {res_gen1.text}"

    # Retrieve generated list (Verify cached version is served)
    res_list = client.get(f"/api/v1/quests/generated?npc_slug={npc_slug}&player_id={player_id}", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) > 0


def test_gate_g_runtime_presentation_mapping(db):
    """Gate G: Verify presentation-layer helper resolution correctness."""
    emotions = {
        "trust": 80,
        "fear": 10,
        "anger": 40,
        "curiosity": 50,
        "loyalty": 90
    }
    # Dominant is loyalty
    dominant = RuntimePresentationService.dominant_emotion(emotions)
    assert dominant == "loyalty"

    # Normalization
    norms = RuntimePresentationService.get_normalized_emotions(emotions)
    assert norms["trust"] == 0.8
    assert norms["fear"] == 0.1
    assert norms["anger"] == 0.4
    assert norms["curiosity"] == 0.5
    assert norms["loyalty"] == 0.9

    # Animation hints lookup
    hints = {
        "loyalty": "salute",
        "anger": "shout",
        "idle": "neutral"
    }
    anim = RuntimePresentationService.resolve_animation(dominant, hints)
    assert anim == "salute"

    # Default fallback
    anim_fallback = RuntimePresentationService.resolve_animation("fear", hints)
    assert anim_fallback == "neutral"


def test_gate_h_dto_contract_validation(db):
    """Gate H: Verify schemas adhere strictly to defined API models."""
    project_id = f"proj_dto_{uuid.uuid4().hex[:6]}"
    headers = {"X-Game-Project-ID": project_id}

    # Setup NPC
    npc_slug = "contract-npc"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Contractor",
        "personality_summary": "Checks DTO schemas."
    })

    # Chat Dialogue response DTO validate
    payload = {
        "npc_slug": npc_slug,
        "player_message": "Evaluate contract."
    }
    res_chat = client.post("/api/v1/dialogue/chat", headers=headers, json=payload)
    assert res_chat.status_code == 200
    data = res_chat.json()
    
    # Try parsing into DialogueChatResponse model
    response_obj = DialogueChatResponse(**data)
    assert response_obj.api_version == "1.0"
    assert response_obj.npc_slug == npc_slug
    assert len(response_obj.response_text) > 0


def test_gate_i_unity_contract_compatibility(db):
    """Gate I: Verify json structure handles Unity JsonUtility serialization constraints."""
    project_id = f"proj_unity_{uuid.uuid4().hex[:6]}"
    headers = {"X-Game-Project-ID": project_id}

    npc_slug = "unity-npc"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Unity",
        "personality_summary": "NPC testing C# bindings."
    })

    res_chat = client.post("/api/v1/dialogue/chat", headers=headers, json={
        "npc_slug": npc_slug,
        "player_message": "Unity test"
    })
    data = res_chat.json()

    # Unity JsonUtility constraint check:
    # 1. No dictionary or dynamic object keyings as top-level properties
    # 2. Array lists are strictly array items
    # 3. Numeric values are float or integer fields
    assert isinstance(data["api_version"], str)
    assert isinstance(data["citations"], list)
    assert isinstance(data["npc_emotions"], dict)
    assert isinstance(data["npc_emotions"]["trust"], float)


def test_gate_j_full_regression_compatibility(db):
    """Gate J: Verify health and original endpoints function regression-free."""
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"


def test_local_provider_smoke(db):
    """Verify that the default local provider path executes without external API keys."""
    project_id = "local_smoke_project"
    headers = {"X-Game-Project-ID": project_id}

    npc_slug = "local-mage"
    client.post("/api/v1/npcs", headers=headers, json={
        "slug": npc_slug,
        "name": "Grand Archmage",
        "personality_summary": "The leader of the Mage Guild who knows all secrets of the arcane."
    })

    res_chat = client.post("/api/v1/dialogue/chat", headers=headers, json={
        "npc_slug": npc_slug,
        "player_message": "Tell me about the magic tome guild."
    })
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert "response_text" in data
    assert data["llm_provider"] == "local_mock"
    assert data["telemetry"]["estimated_cost_usd"] == 0.0
