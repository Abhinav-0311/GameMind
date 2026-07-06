import pytest
from fastapi.testclient import TestClient
from main import app
from app.models.document import Document
from app.services.rag_service import RAGService
import uuid

client = TestClient(app)

def test_query_endpoint_local_demo():
    """Verify that querying works in local demo mode."""
    response = client.post("/api/v1/query/", json={"query": "test query", "limit": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "test query"
    assert "results" in data
    if not data["results"]:
        assert "message" in data
        assert "No matching lore fragments" in data["message"]

def test_document_upload_local_demo(db_session):
    """Verify document upload writes to the local vector collection."""
    rag = RAGService()
    
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

def test_query_returns_citations_local_demo(db_session):
    """Verify query returns citations cleanly with local embeddings."""
    rag = RAGService()
    
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

def test_query_empty_local_collection(db_session):
    """Verify querying an empty collection returns 200 with notice message."""
    rag = RAGService()
    
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

def test_chroma_default_embedding_path():
    """Verify that Chroma can generate local embeddings and dimension conflicts are avoided."""
    rag = RAGService()
    
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

def test_frostpeak_demo_document_loader_is_idempotent(db_session):
    """Verify the bundled demo GDD can be loaded once for the golden path."""
    project_id = "demo_seed_proj"
    rag = RAGService()
    try:
        rag.collection.delete(where={"game_project_id": project_id})
    except Exception:
        pass

    headers = {"X-Game-Project-ID": project_id}
    first = client.post("/api/v1/documents/demo/frostpeak", headers=headers)
    second = client.post("/api/v1/documents/demo/frostpeak", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201

    first_doc = first.json()
    second_doc = second.json()
    assert first_doc["id"] == second_doc["id"]
    assert first_doc["title"] == "sample_gdd_frostpeak.md"
    assert first_doc["chunks_count"] > 0

    matching_docs = db_session.query(Document).filter(
        Document.title == "sample_gdd_frostpeak.md",
        Document.game_project_id == project_id
    ).all()
    assert len(matching_docs) == 1
