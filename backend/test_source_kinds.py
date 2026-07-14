import uuid

from fastapi.testclient import TestClient

from app.services.rag_service import RAGService
from main import app


client = TestClient(app)


def test_source_kind_is_classified_and_can_be_overridden(db_session):
    project_id = f"source_kind_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="characters.md",
        file_bytes=b"# NPC Profiles\nNPC Elara is a cartographer with guarded dialogue.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    assert document.source_kind == "npc_sheet"

    response = client.put(
        f"/api/v1/documents/{document.id}/source-kind",
        headers={"X-Game-Project-ID": project_id},
        json={"source_kind": "lore"},
    )
    assert response.status_code == 200
    assert response.json()["source_kind"] == "lore"


def test_source_kind_override_enforces_project_scope(db_session):
    project_id = f"source_kind_owner_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="notes.md",
        file_bytes=b"General development notes.",
        content_type="text/markdown",
        game_project_id=project_id,
    )

    response = client.put(
        f"/api/v1/documents/{document.id}/source-kind",
        headers={"X-Game-Project-ID": "wrong_project"},
        json={"source_kind": "gdd"},
    )
    assert response.status_code == 404
