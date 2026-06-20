from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.document import Document, DocumentChunk
import uuid
import pytest

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="module")
def setup_data(db_session):
    # Create test NPC
    npc_slug = f"test_wizard_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Zephyr",
        title="Keeper of Wind",
        personality_summary="A calm and quiet wizard who values freedom and wind magic.",
        dialogue_style="Whispers gently, speaks in brief poetic remarks.",
        voice_profile="soft-breeze",
        faction_alignment="zephyr_sect",
        animation_hints={"neutral": "float_idle"},
        memory_settings={"search_threshold": 0.5}
    )
    db_session.add(npc)

    # Create missing faction NPC
    npc_missing_fac_slug = f"test_wanderer_{uuid.uuid4().hex[:6]}"
    npc_missing_fac = NPCProfile(
        slug=npc_missing_fac_slug,
        name="Logan",
        title=None,
        personality_summary="A lone wanderer.",
        dialogue_style=None,
        voice_profile=None,
        faction_alignment=None,
        animation_hints=None,
        memory_settings=None
    )
    db_session.add(npc_missing_fac)

    import datetime
    # Create a soft-deleted NPC
    deleted_npc_slug = f"test_ghost_{uuid.uuid4().hex[:6]}"
    deleted_npc = NPCProfile(
        slug=deleted_npc_slug,
        name="Phantasm",
        personality_summary="A ghost.",
        deleted_at=datetime.datetime.now(datetime.timezone.utc) # Mock deleted timestamp
    )
    db_session.add(deleted_npc)

    # Create a test document and chunks
    doc = Document(
        title="Wind Tome",
        content_type="text/plain"
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="The Wind Tome describes Ember Siege as a tragic event where fire swallowed the watchtower.",
        metadata={"title": "Wind Tome"}
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=1,
        content="Zephyr was absent during the siege because he was communing with the sky spirits.",
        metadata={"title": "Wind Tome"}
    )
    db_session.add(chunk1)
    db_session.add(chunk2)

    db_session.commit()

    return {
        "npc_slug": npc_slug,
        "npc_missing_fac_slug": npc_missing_fac_slug,
        "deleted_npc_slug": deleted_npc_slug,
        "chunk1_id": str(chunk1.id),
        "chunk2_id": str(chunk2.id),
        "chunk1_content": chunk1.content,
        "chunk2_content": chunk2.content
    }

def test_npc_character_consistency(setup_data):
    """Verify that the NPC personality guidelines are injected into the context."""
    payload = {
        "npc_slug": setup_data["npc_slug"],
        "player_message": "Hello Zephyr.",
        "selected_chunk_ids": []
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["npc_slug"] == setup_data["npc_slug"]
    assert "Zephyr" in data["npc_context"]
    assert "Keeper of Wind" in data["npc_context"]
    assert "A calm and quiet wizard" in data["npc_context"]
    assert "Whispers gently" in data["npc_context"]
    assert "v1" == data["prompt_version"]

def test_unsupported_claim_refusal_instruction(setup_data):
    """Verify the prompt forces refusal of unsupported lore claims."""
    payload = {
        "npc_slug": setup_data["npc_slug"],
        "player_message": "Tell me about the siege.",
        "selected_chunk_ids": []
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Refuse unsupported claims" in data["system_prompt"]
    assert "must state that you do not know or refuse to answer" in data["system_prompt"]

def test_retrieved_lore_context_assembly(setup_data):
    """Verify multiple database chunks are retrieved and constructed in context."""
    payload = {
        "npc_slug": setup_data["npc_slug"],
        "player_message": "What happened to you during the siege?",
        "selected_chunk_ids": [setup_data["chunk1_id"], setup_data["chunk2_id"]]
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["retrieved_chunk_count"] == 2
    assert setup_data["chunk1_content"] in data["retrieved_context"]
    assert setup_data["chunk2_content"] in data["retrieved_context"]
    assert len(data["retrieved_chunks"]) == 2
    assert data["retrieved_chunks"][0]["chunk_index"] == 0
    assert data["retrieved_chunks"][1]["chunk_index"] == 1

def test_empty_retrieved_lore_context(setup_data):
    """Verify dialog behaves cleanly when no lore chunks are requested."""
    payload = {
        "npc_slug": setup_data["npc_slug"],
        "player_message": "Where are you?",
        "selected_chunk_ids": []
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["retrieved_chunk_count"] == 0
    assert "No relevant lore chunks provided" in data["retrieved_context"]

def test_missing_faction_alignment_graceful_formatting(setup_data):
    """Verify that NPCs without faction alignments assemble successfully without formatting bugs."""
    payload = {
        "npc_slug": setup_data["npc_missing_fac_slug"],
        "player_message": "Hello traveller.",
        "selected_chunk_ids": []
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["npc_slug"] == setup_data["npc_missing_fac_slug"]
    assert "Faction Alignment: UNALIGNED" in data["npc_context"]
    assert "Dialogue Style Guidelines: n/a" in data["npc_context"]

def test_deleted_npc_profile_rejection(setup_data):
    """Verify soft-deleted NPC requests return a clean 404 error."""
    payload = {
        "npc_slug": setup_data["deleted_npc_slug"],
        "player_message": "Can you hear me?",
        "selected_chunk_ids": []
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 404
    assert "not found or has been deleted" in response.json()["detail"]

def test_oversized_player_message_truncation(setup_data):
    """Verify oversized player messages are truncated to 4000 characters and throw warnings."""
    huge_message = "A" * 20000
    payload = {
        "npc_slug": setup_data["npc_slug"],
        "player_message": huge_message,
        "selected_chunk_ids": []
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["player_message"]) == 4000
    assert any("Player message truncated from 20000 to 4000" in w for w in data["warnings"])
    assert data["estimated_tokens"] > 0
    assert data["character_count"] == len(data["assembled_prompt"])

def test_context_window_overflow_truncation(setup_data, db_session):
    """Verify that chunks are truncated if the total context size exceeds 8000 characters."""
    doc = Document(title="Large Tome", content_type="text/plain")
    db_session.add(doc)
    db_session.flush()
    
    # Create very large chunks (e.g. 5000 characters each)
    chunkA = DocumentChunk(id=uuid.uuid4(), document_id=doc.id, chunk_index=0, content="A" * 5000, metadata={"title": "Large Tome"})
    chunkB = DocumentChunk(id=uuid.uuid4(), document_id=doc.id, chunk_index=1, content="B" * 5000, metadata={"title": "Large Tome"})
    db_session.add(chunkA)
    db_session.add(chunkB)
    db_session.commit()

    payload = {
        "npc_slug": setup_data["npc_slug"],
        "player_message": "Short message.",
        "selected_chunk_ids": [str(chunkA.id), str(chunkB.id)]
    }
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["retrieved_context"]) <= 8200 # approx 8000 + formatting title boundary
    assert any("context truncated to 8000 characters" in w for w in data["warnings"])
