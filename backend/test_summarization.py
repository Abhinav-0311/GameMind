import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.session import Conversation, Message
from app.models.memory import NPCMemory
from app.services.memory_service import MemoryService
from unittest.mock import patch, MagicMock
import uuid
import datetime
import json

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

def test_message_threshold_trigger(db):
    # Setup test NPC
    npc_slug = f"test_seer_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Seraphina",
        personality_summary="A mystic seer."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    # 1. Create a conversation
    conv_response = client.post("/api/v1/conversations", json={"npc_slug": npc_slug})
    assert conv_response.status_code == 201
    conv_id = conv_response.json()["id"]

    # Mock the LLM provider for the background summarization task
    mock_provider = MagicMock()
    async def mock_resp(*args, **kwargs):
        return (json.dumps({
            "summary": "This is a mock summary of the Seraphina chat.",
            "extracted_memories": [
                {"text": "Seraphina saw a vision of a rising moon.", "type": "episodic", "importance_score": 8.0},
                {"text": "Omitted low importance memory.", "type": "episodic", "importance_score": 3.0}
            ]
        }), {})
    mock_provider.generate_response.side_effect = mock_resp

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        # We also mock retrieve_memories to prevent it from failing on empty vector db
        with patch.object(MemoryService, "retrieve_memories", return_value="No relevant memories."):
            # We mock index_memory_in_chroma to succeed normally
            with patch.object(MemoryService, "index_memory_in_chroma") as mock_index:
                # Send 5 chat requests (Player + NPC response = 10 messages)
                for i in range(5):
                    chat_response = client.post("/api/v1/dialogue/chat", json={
                        "npc_slug": npc_slug,
                        "player_message": f"Message turn {i}",
                        "conversation_id": conv_id,
                        "selected_chunk_ids": []
                    })
                    assert chat_response.status_code == 200

                # Verify that the background task was scheduled and completed
                db.expire_all()
                conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
                assert conv.conversation_summary == "This is a mock summary of the Seraphina chat."
                assert conv.summary_version == 1
                assert conv.summary_updated_at is not None
                assert conv.last_summarized_message_id is not None
                
                # Check promoted memories
                promoted_mems = db.query(NPCMemory).filter(NPCMemory.npc_id == npc.id).all()
                # Expect ONLY the memory with score 8.0 to be saved (rejections < 5.0 are omitted)
                assert len(promoted_mems) == 1
                assert promoted_mems[0].memory_text == "Seraphina saw a vision of a rising moon."
                assert promoted_mems[0].importance_score == 8.0
                assert promoted_mems[0].archived is False

def test_character_threshold_trigger(db):
    npc_slug = f"test_bard_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Elidor",
        personality_summary="A bard."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    conv_response = client.post("/api/v1/conversations", json={"npc_slug": npc_slug})
    conv_id = conv_response.json()["id"]

    mock_provider = MagicMock()
    async def mock_resp(*args, **kwargs):
        return (json.dumps({
            "summary": "This is a summary triggered by character length.",
            "extracted_memories": []
        }), {})
    mock_provider.generate_response.side_effect = mock_resp

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        with patch.object(MemoryService, "retrieve_memories", return_value="No relevant memories."):
            # Send one very large player message (e.g. 6,100 characters) which immediately triggers the character threshold
            large_message = "A" * 6100
            chat_response = client.post("/api/v1/dialogue/chat", json={
                "npc_slug": npc_slug,
                "player_message": large_message,
                "conversation_id": conv_id,
                "selected_chunk_ids": []
            })
            assert chat_response.status_code == 200

            # Verify character threshold trigger worked
            db.expire_all()
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            assert conv.conversation_summary == "This is a summary triggered by character length."
            assert conv.summary_version == 1

def test_chroma_indexing_failure_recovery_in_background(db):
    npc_slug = f"test_guard_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Garrick",
        personality_summary="A loyal guard."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    conv_response = client.post("/api/v1/conversations", json={"npc_slug": npc_slug})
    conv_id = conv_response.json()["id"]

    mock_provider = MagicMock()
    async def mock_resp(*args, **kwargs):
        return (json.dumps({
            "summary": "Garrick summary.",
            "extracted_memories": [
                {"text": "Garrick defended the gates.", "type": "episodic", "importance_score": 9.0}
            ]
        }), {})
    mock_provider.generate_response.side_effect = mock_resp

    # Mock index_memory_in_chroma to raise an exception, simulating indexing failure
    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        with patch.object(MemoryService, "retrieve_memories", return_value="No relevant memories."):
            with patch.object(MemoryService, "index_memory_in_chroma", side_effect=Exception("Chroma Offline")):
                # Send 5 requests to exceed 10 messages trigger
                for i in range(5):
                    client.post("/api/v1/dialogue/chat", json={
                        "npc_slug": npc_slug,
                        "player_message": f"Guard turn {i}",
                        "conversation_id": conv_id,
                        "selected_chunk_ids": []
                    })
                
                db.expire_all()
                # Confirm memory was committed to Postgres but has chroma_indexed = False
                db_mems = db.query(NPCMemory).filter(NPCMemory.npc_id == npc.id).all()
                assert len(db_mems) == 1
                assert db_mems[0].memory_text == "Garrick defended the gates."
                assert db_mems[0].chroma_indexed is False

def test_summarization_failure_resiliency(db):
    npc_slug = f"test_mage_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Eldrin",
        personality_summary="A mage."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    conv_response = client.post("/api/v1/conversations", json={"npc_slug": npc_slug})
    conv_id = conv_response.json()["id"]

    # Mock provider to raise exception during background execution
    mock_provider = MagicMock()
    async def mock_fail(*args, **kwargs):
        raise Exception("Provider Rate Limit Exceeded")
    mock_provider.generate_response.side_effect = mock_fail

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        with patch.object(MemoryService, "retrieve_memories", return_value="No relevant memories."):
            # Trigger summarization with 5 chat messages (10 messages total)
            # The first 4 turns should succeed
            for i in range(4):
                client.post("/api/v1/dialogue/chat", json={
                    "npc_slug": npc_slug,
                    "player_message": f"Mage turn {i}",
                    "conversation_id": conv_id,
                    "selected_chunk_ids": []
                })
            
            # The 5th turn triggers the background task which raises the exception.
            # In TestClient, this exception propagates back to the caller.
            with pytest.raises(Exception, match="Provider Rate Limit Exceeded"):
                client.post("/api/v1/dialogue/chat", json={
                    "npc_slug": npc_slug,
                    "player_message": "Mage turn 4",
                    "conversation_id": conv_id,
                    "selected_chunk_ids": []
                })
            
            db.expire_all()
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            # Summary should remain NULL/0 because the background task failed
            assert conv.conversation_summary is None
            assert conv.summary_version == 0
            assert conv.last_summarized_message_id is None

def test_archive_only_consolidation(db):
    # Setup test NPC
    npc_slug = f"test_thief_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Robin",
        personality_summary="A thief."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    # Insert 3 similar memories
    mem1 = NPCMemory(
        npc_id=npc.id,
        memory_text="Robin stole a gold coin.",
        importance_score=4.0,
        chroma_indexed=True,
        archived=False
    )
    mem2 = NPCMemory(
        npc_id=npc.id,
        memory_text="Robin stole gold coins.",
        importance_score=8.5, # Highest importance
        chroma_indexed=True,
        archived=False
    )
    mem3 = NPCMemory(
        npc_id=npc.id,
        memory_text="Robin stole a gold coin from sheriff.",
        importance_score=6.0,
        chroma_indexed=True,
        archived=False
    )
    db.add_all([mem1, mem2, mem3])
    db.commit()
    for m in [mem1, mem2, mem3]:
        db.refresh(m)

    # Mock Chroma collection get to return similar mock embeddings (causing similarity >= 0.85)
    mock_embeddings = {
        str(mem1.id): [0.1] * 768,
        str(mem2.id): [0.1001] * 768, # Extremely close
        str(mem3.id): [0.0999] * 768  # Extremely close
    }

    rag = MagicMock()
    mem_service = MemoryService(rag)
    
    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": [str(mem1.id), str(mem2.id), str(mem3.id)],
        "embeddings": [[0.1] * 768, [0.1001] * 768, [0.0999] * 768]
    }
    mem_service.memory_collection = mock_collection

    # Trigger consolidation endpoint
    from app.api.v1.memories import get_memory_service
    app.dependency_overrides[get_memory_service] = lambda: mem_service
    try:
        response = client.post("/api/v1/memories/consolidate", json={"npc_slug": npc_slug})
        assert response.status_code == 200
        data = response.json()
        assert data["clusters_processed"] == 1
        assert data["archived_memories_count"] == 2

        # Verify DB changes
        db.refresh(mem1)
        db.refresh(mem2)
        db.refresh(mem3)

        # mem2 (importance 8.5) should be retained active
        assert mem2.archived is False
        
        # mem1 (4.0) and mem3 (6.0) should be archived
        assert mem1.archived is True
        assert mem3.archived is True
        assert mem1.chroma_indexed is False
        assert mem3.chroma_indexed is False

        # Verify duplicate deletions were triggered on Chroma collection
        assert mock_collection.delete.call_count == 2
    finally:
        app.dependency_overrides.pop(get_memory_service, None)
