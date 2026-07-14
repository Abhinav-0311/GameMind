import uuid

from fastapi.testclient import TestClient

from app.services.rag_service import RAGService
from main import app


client = TestClient(app)


def test_blueprint_provenance_resolves_section_citations(db_session):
    project_id = f"provenance_{uuid.uuid4().hex[:8]}"
    source = RAGService().process_document(
        db=db_session,
        file_name="provenance_gdd.md",
        file_bytes=b"# GDD\nOverview: Restore the flooded observatory for the northern guild.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    headers = {"X-Game-Project-ID": project_id}
    generated = client.post("/api/v1/blueprints/generate", headers=headers, json={"document_id": str(source.id)})
    assert generated.status_code == 201

    response = client.get(f"/api/v1/blueprints/{generated.json()['id']}/provenance", headers=headers)
    assert response.status_code == 200
    summary = next(section for section in response.json()["sections"] if section["section"] == "summary")
    assert summary["citations"]
    assert summary["citations"][0]["document_title"] == "provenance_gdd.md"
    assert summary["citations"][0]["revision_number"] == 1


def test_blueprint_provenance_enforces_project_scope(db_session):
    project_id = f"provenance_owner_{uuid.uuid4().hex[:8]}"
    source = RAGService().process_document(
        db=db_session,
        file_name="private_gdd.md",
        file_bytes=b"Overview: A private project.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    generated = client.post(
        "/api/v1/blueprints/generate",
        headers={"X-Game-Project-ID": project_id},
        json={"document_id": str(source.id)},
    )

    response = client.get(
        f"/api/v1/blueprints/{generated.json()['id']}/provenance",
        headers={"X-Game-Project-ID": "another_project"},
    )
    assert response.status_code == 404
