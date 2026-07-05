import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.memory import NPCMemory
from app.services.rag_service import RAGService
from app.services.memory_service import MemoryService
from unittest.mock import MagicMock, patch
import uuid
import datetime

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

def test_memory_crud_operations(db):
    # Setup test NPC
    npc_slug = f"test_thief_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Robin",
        personality_summary="A thief who steals from the rich."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    # 1. Test POST /api/v1/memories endpoint
    payload = {
        "npc_slug": npc_slug,
        "memory_text": "Robin stole a gold coin from the sheriff.",
        "memory_type": "episodic",
        "importance_score": 7.5
    }
    
    response = client.post("/api/v1/memories", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["memory_text"] == payload["memory_text"]
    assert data["chroma_indexed"] is True
    mem_id = data["id"]

    # Check DB directly
    db_mem = db.query(NPCMemory).filter(NPCMemory.id == mem_id).first()
    assert db_mem is not None
    assert db_mem.memory_text == payload["memory_text"]
    assert db_mem.importance_score == 7.5
    assert db_mem.chroma_indexed is True

def test_memory_indexing_failure_and_sync(db):
    npc_slug = f"test_guard_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Garrick",
        personality_summary="A loyal guard."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    # 1. Test indexing failure recovery
    rag = RAGService()
    mem_service = MemoryService(rag)
    
    # Force chroma collection addition to fail
    mem_service.memory_collection = MagicMock()
    mem_service.memory_collection.add.side_effect = Exception("Chroma Connection Timed Out")

    # Run service call
    db_mem = mem_service.create_memory(
        db=db,
        npc_id=npc.id,
        memory_text="Garrick guarded the royal vault.",
        importance_score=4.0
    )
    
    # Verify PostgreSQL committed successfully but chroma_indexed is False
    assert db_mem.id is not None
    assert db_mem.chroma_indexed is False

    # Check directly from DB
    db_record = db.query(NPCMemory).filter(NPCMemory.id == db_mem.id).first()
    assert db_record is not None
    assert db_record.chroma_indexed is False

    # 2. Test manual sync API sweeps and resolves the index
    mem_service.memory_collection.add.side_effect = None
    mem_service.memory_collection.add.reset_mock()
    
    # Run sync trigger via endpoint using FastAPI overrides
    from app.api.v1.memories import get_memory_service
    app.dependency_overrides[get_memory_service] = lambda: mem_service
    try:
        sync_response = client.post("/api/v1/memories/sync")
        assert sync_response.status_code == 200
        sync_data = sync_response.json()
        assert sync_data["processed"] >= 1
        assert sync_data["failed"] == 0

        # Verify DB updated
        db.refresh(db_record)
        assert db_record.chroma_indexed is True
        mem_service.memory_collection.add.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_memory_service, None)

def test_composite_retrieval_ranking(db):
    npc_slug = f"test_sage_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Gideon",
        personality_summary="A wise sage."
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    rag = RAGService()
    mem_service = MemoryService(rag)

    # Mock Chroma collection query to return mock distances/ids
    cand1_id = uuid.uuid4()
    cand2_id = uuid.uuid4()
    cand3_id = uuid.uuid4()
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    mem1 = NPCMemory(
        id=cand1_id,
        npc_id=npc.id,
        memory_text="Scroll of Fire matches search.",
        importance_score=2.0,
        chroma_indexed=True,
        created_at=now - datetime.timedelta(hours=24)
    )
    mem2 = NPCMemory(
        id=cand2_id,
        npc_id=npc.id,
        memory_text="The Crown Jewel of Frostpeak is hidden.",
        importance_score=10.0,
        chroma_indexed=True,
        created_at=now
    )
    mem3 = NPCMemory(
        id=cand3_id,
        npc_id=npc.id,
        memory_text="Lute song has magic.",
        importance_score=5.0,
        chroma_indexed=True,
        created_at=now - datetime.timedelta(hours=48)
    )
    db.add_all([mem1, mem2, mem3])
    db.commit()

    # Mock Chroma queries output
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [[str(cand1_id), str(cand2_id), str(cand3_id)]],
        "distances": [[0.1, 0.3, 0.6]],
        "documents": [["Scroll of Fire matches search.", "The Crown Jewel of Frostpeak is hidden.", "Lute song has magic."]],
        "metadatas": [[{}, {}, {}]]
    }
    mem_service.memory_collection = mock_collection
    
    # Expect ranking score order: Memory 2 (0.85) > Memory 1 (0.66) > Memory 3 (0.49)
    retrieved_text = mem_service.retrieve_memories(db, npc.id, "crown jewel", limit=3)
    
    # Check that retrieved text orders them: Memory 2 then Memory 1 then Memory 3
    lines = retrieved_text.split("\n")
    assert len(lines) == 3
    assert "The Crown Jewel" in lines[0]
    assert "Scroll of Fire" in lines[1]
    assert "Lute song" in lines[2]
