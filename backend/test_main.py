from fastapi.testclient import TestClient
from main import app
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService
import uuid

client = TestClient(app)

def test_health_endpoint():
    """Verify that health check returns 200 and details status fields."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "chromadb" in data
    assert "gemini_api" in data

def test_chunker_logic():
    """Verify that chunking divides text within bounds and handles overlap correctly."""
    gemini = GeminiService()
    rag = RAGService(gemini)
    text = "This is a sentence. And here is another sentence that is longer. " * 20
    chunks = rag.chunk_text(text, chunk_size=100, chunk_overlap=20)
    
    assert len(chunks) > 0
    # Every chunk should be under our limit
    for chunk in chunks:
        assert len(chunk) <= 100
        assert len(chunk) > 0

def test_npc_lifecycle():
    """Verify create, validate, list, fetch, update, and soft-delete lifecycle of NPCs."""
    unique_slug = f"eldrin_mage_{uuid.uuid4().hex[:6]}"
    payload = {
        "slug": unique_slug,
        "name": "Eldrin",
        "title": "Archmage of the Watchtower",
        "personality_summary": "Cautious and scholarly librarian who speaks in warning tones.",
        "dialogue_style": "Uses formal language, hesitates frequently, and references history.",
        "voice_profile": "elderly-gravelly-english",
        "faction_alignment": "cinder_vanguard",
        "animation_hints": {"neutral": "idle_read", "concerned": "shake_head"},
        "memory_settings": {"search_threshold": 0.65},
        "metadata": {"custom_tag": "test-npc"}
    }
    
    # 1. Create NPC profile
    response = client.post("/api/v1/npcs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == unique_slug
    assert data["name"] == "Eldrin"
    assert "id" in data
    npc_id = data["id"]

    # 2. Invalid slug rejection: too short
    payload_invalid_len = payload.copy()
    payload_invalid_len["slug"] = "el"
    response = client.post("/api/v1/npcs", json=payload_invalid_len)
    assert response.status_code == 422  # Pydantic validation error

    # Invalid slug rejection: invalid characters (uppercase / punctuation)
    payload_invalid_chars = payload.copy()
    payload_invalid_chars["slug"] = "Eldrin_Mage!"
    response = client.post("/api/v1/npcs", json=payload_invalid_chars)
    assert response.status_code == 422

    # 3. Duplicate slug rejection
    response = client.post("/api/v1/npcs", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

    # 4. List NPC profiles
    response = client.get("/api/v1/npcs")
    assert response.status_code == 200
    npcs = response.json()
    assert any(n["id"] == npc_id for n in npcs)

    # 5. Fetch NPC by ID
    response = client.get(f"/api/v1/npcs/{npc_id}")
    assert response.status_code == 200
    assert response.json()["slug"] == unique_slug

    # 6. Update NPC profile
    update_payload = {
        "title": "Grand Archmage of the Watchtower",
        "personality_summary": "Extremely cautious and scholarly librarian.",
        "metadata": {"updated_tag": "test-npc-updated"}
    }
    response = client.put(f"/api/v1/npcs/{npc_id}", json=update_payload)
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["title"] == "Grand Archmage of the Watchtower"
    assert updated_data["personality_summary"] == "Extremely cautious and scholarly librarian."
    assert updated_data["metadata"]["updated_tag"] == "test-npc-updated"
    assert updated_data["name"] == "Eldrin"  # verify name remains unchanged

    # 7. Soft delete NPC
    response = client.delete(f"/api/v1/npcs/{npc_id}")
    assert response.status_code == 200
    assert "soft-deleted successfully" in response.json()["message"]

    # 8. Verify deleted NPC no longer appears in listings
    response = client.get("/api/v1/npcs")
    assert response.status_code == 200
    npcs_after = response.json()
    assert not any(n["id"] == npc_id for n in npcs_after)

    # 9. Verify deleted NPC returns 404 on GET by ID
    response = client.get(f"/api/v1/npcs/{npc_id}")
    assert response.status_code == 404

