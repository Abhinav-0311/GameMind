import uuid

from fastapi.testclient import TestClient

from app.services.rag_service import RAGService
from main import app


client = TestClient(app)


def test_blueprint_brief_exports_source_grounded_markdown(db_session):
    project_id = f"brief_{uuid.uuid4().hex[:8]}"
    source = RAGService().process_document(
        db=db_session,
        file_name="brief_gdd.md",
        file_bytes=b"# GDD\nOverview: Rebuild the lighthouse to guide the northern fleet.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    headers = {"X-Game-Project-ID": project_id}
    generated = client.post("/api/v1/blueprints/generate", headers=headers, json={"document_id": str(source.id)})
    assert generated.status_code == 201

    response = client.get(f"/api/v1/blueprints/{generated.json()['id']}/brief", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# Blueprint: brief_gdd.md" in response.text
    assert "## Sources" in response.text
    assert "brief_gdd.md (revision 1" in response.text
    assert "## Game summary" in response.text


def test_blueprint_brief_enforces_project_scope(db_session):
    project_id = f"brief_owner_{uuid.uuid4().hex[:8]}"
    source = RAGService().process_document(
        db=db_session,
        file_name="private_brief.md",
        file_bytes=b"Overview: Private work.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    generated = client.post(
        "/api/v1/blueprints/generate",
        headers={"X-Game-Project-ID": project_id},
        json={"document_id": str(source.id)},
    )

    response = client.get(
        f"/api/v1/blueprints/{generated.json()['id']}/brief",
        headers={"X-Game-Project-ID": "another_project"},
    )
    assert response.status_code == 404
