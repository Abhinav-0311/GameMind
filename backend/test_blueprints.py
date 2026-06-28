import pytest
from fastapi.testclient import TestClient
from main import app
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService
from app.models.document import Document
from app.models.blueprint import GameBlueprint
import uuid

client = TestClient(app)

@pytest.fixture
def uploaded_document(db_session):
    """Fixture to upload a sample GDD document for testing."""
    gemini = GeminiService()
    rag = RAGService(gemini)
    
    file_name = f"gdd_test_{uuid.uuid4().hex[:6]}.txt"
    file_bytes = (
        b"# GDD Summary\n"
        b"Overview: A game about exploring cold towers.\n"
        b"# Art Style\n"
        b"Visual Theme: Stylized dark fantasy visual elements.\n"
        b"# NPC Profiles\n"
        b"NPC Eldrin: A wise old librarian archmage.\n"
        b"# Level Design\n"
        b"Level Geothermal Vents: active vents and locked East Gate.\n"
        b"# Quest Hooks\n"
        b"Quest Hook 1: Objective: Reclaim Ash Pass."
    )
    
    doc = rag.process_document(
        db=db_session,
        file_name=file_name,
        file_bytes=file_bytes,
        content_type="text/plain",
        game_project_id="test_project_alpha"
    )
    return doc

def test_generate_blueprint_success(uploaded_document):
    """Test generating a game blueprint from an existing GDD document succeeds."""
    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == f"Blueprint: {uploaded_document.title}"
    assert data["game_project_id"] == "test_project_alpha"
    assert data["status"] == "draft"
    
    # Assert all 8 sections are populated
    for section in ["summary", "narrative_direction", "art_style_direction", "npc_archetypes", 
                    "npc_memory_design", "level_design_suggestions", "quest_hooks", "unity_runtime_preview"]:
        assert section in data
        assert "content" in data[section]
        assert "citations" in data[section]
        assert "confidence" in data[section]
        assert "warnings" in data[section]

def test_approve_blueprint_success(uploaded_document):
    """Test approving a game blueprint updates its status to 'approved'."""
    # 1. Generate
    gen_response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    blueprint_id = gen_response.json()["id"]

    # 2. Approve
    app_response = client.put(
        f"/api/v1/blueprints/{blueprint_id}/approve",
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert app_response.status_code == 200
    assert app_response.json()["status"] == "approved"

def test_export_blueprint_success(uploaded_document):
    """Test exporting a game blueprint yields valid Unity runtime JSON."""
    # 1. Generate
    gen_response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    blueprint_id = gen_response.json()["id"]

    # 2. Export
    exp_response = client.get(
        f"/api/v1/blueprints/{blueprint_id}/export",
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert exp_response.status_code == 200
    data = exp_response.json()
    assert data["api_version"] == "1.0"
    assert data["game_project_id"] == "test_project_alpha"
    assert "runtime_data" in data
    
    # Verify runtime elements are present
    runtime = data["runtime_data"]
    assert "game_summary" in runtime
    assert "art_style" in runtime
    assert "npcs" in runtime
    assert "levels" in runtime
    assert "quests" in runtime

def test_project_scoping_enforcement(uploaded_document):
    """Test that blueprints enforce strict project-scoped ownership boundaries."""
    # Try generating a blueprint with a different game_project_id (X-Game-Project-ID: project_beta)
    # This should fail because the document belongs to test_project_alpha
    gen_response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "project_beta"}
    )
    assert gen_response.status_code == 404
    assert "not owned by this project" in gen_response.json()["detail"]

def test_missing_input_warnings_and_citations(uploaded_document):
    """Test that missing GDD section content generates template warnings and correct citations."""
    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert response.status_code == 201
    data = response.json()
    
    # Summary should be high confidence (present in GDD text)
    assert data["summary"]["confidence"] == "High"
    assert len(data["summary"]["citations"]) > 0
    
    # NPC Memory should trigger template fallback warning since the text did not contain memory keywords
    assert data["npc_memory_design"]["confidence"] == "Low"
    assert len(data["npc_memory_design"]["warnings"]) > 0
    assert "No key event memory configurations" in data["npc_memory_design"]["warnings"][0]
