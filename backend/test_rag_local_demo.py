import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from main import app
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService
from app.database import SessionLocal
import uuid

client = TestClient(app)

@pytest.fixture
def mock_gemini_unavailable(monkeypatch):
    """Fixture to mock GeminiService as unavailable/unconfigured."""
    monkeypatch.setattr(GeminiService, "is_available", lambda self: False)
    monkeypatch.setattr(GeminiService, "generate_embedding", lambda self, text: [0.0] * 768)
    monkeypatch.setattr(GeminiService, "generate_batch_embeddings", lambda self, texts: [[0.0] * 768] * len(texts))

def test_query_endpoint_without_gemini(mock_gemini_unavailable):
    """Verify that querying does not return 503 when Gemini is unavailable."""
    response = client.post("/api/v1/query/", json={"query": "test query", "limit": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "test query"
    assert "results" in data
    if not data["results"]:
        assert "message" in data
        assert "No matching lore fragments" in data["message"]

def test_document_upload_without_gemini(mock_gemini_unavailable, db_session):
    """Verify document upload writes to local vector collection when Gemini is unavailable."""
    gemini = GeminiService()
    rag = RAGService(gemini)
    
    assert rag.collection_name == "lore_chunks_local"
    assert rag.collection is not None
    
    file_name = f"test_lore_{uuid.uuid4().hex[:6]}.txt"
    file_bytes = b"This is some local test lore about the Ember Siege."
    doc = rag.process_document(
        db=db_session,
        file_name=file_name,
        file_bytes=file_bytes,
        content_type="text/plain",
        game_project_id="test_local_proj"
    )
    
    assert doc.id is not None
    assert doc.title == file_name
    
    chroma_res = rag.collection.get(
        where={"game_project_id": "test_local_proj"}
    )
    assert len(chroma_res["ids"]) > 0
    assert chroma_res["documents"][0] == "This is some local test lore about the Ember Siege."

def test_query_returns_citations_without_gemini(mock_gemini_unavailable, db_session):
    """Verify query returns citations cleanly without Gemini."""
    gemini = GeminiService()
    rag = RAGService(gemini)
    
    try:
        rag.collection.delete(where={"game_project_id": "test_citation_proj"})
    except Exception:
        pass
        
    file_name = "siege_history.txt"
    file_bytes = b"King Arven ruled during the siege of Frostpeak."
    rag.process_document(
        db=db_session,
        file_name=file_name,
        file_bytes=file_bytes,
        content_type="text/plain",
        game_project_id="test_citation_proj"
    )
    
    results = rag.query_lore(
        query_text="King Arven",
        limit=2,
        game_project_id="test_citation_proj"
    )
    
    assert len(results) > 0
    assert results[0]["title"] == file_name
    assert "content" in results[0]
    assert "similarity" in results[0]
    assert "confidence" in results[0]

def test_query_empty_local_collection(mock_gemini_unavailable, db_session):
    """Verify querying an empty collection returns 200 with notice message."""
    gemini = GeminiService()
    rag = RAGService(gemini)
    
    try:
        rag.collection.delete(where={"game_project_id": "empty_proj"})
    except Exception:
        pass
        
    response = client.post(
        "/api/v1/query/",
        json={"query": "random query text", "limit": 2},
        headers={"X-Game-Project-ID": "empty_proj"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert "message" in data
    assert "No matching lore fragments" in data["message"]

def test_chroma_default_embedding_path(mock_gemini_unavailable):
    """Verify that Chroma can generate local embeddings and dimension conflicts are avoided."""
    gemini = GeminiService()
    rag = RAGService(gemini)
    
    assert rag.collection_name == "lore_chunks_local"
    
    count = rag.collection.count()
    assert isinstance(count, int)

    response = client.get("/health")
    assert response.status_code == 200
    health_data = response.json()
    assert health_data["ai_mode"] == "local_demo"
    assert health_data["vector_collection"] == "lore_chunks_local"
    # Assert vector_dimension from health metadata directly
    assert "vector_dimension" in health_data
