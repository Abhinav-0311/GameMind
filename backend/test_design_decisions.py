import uuid

from fastapi.testclient import TestClient

from app.services.rag_service import RAGService
from main import app


client = TestClient(app)


def test_sync_and_resolve_design_decision(db_session):
    project_id = f"decision_project_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="decision_source.md",
        file_bytes=b"# Prototype\nA puzzle game with one quest objective: restore the beacon.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    headers = {"X-Game-Project-ID": project_id}

    first_sync = client.post("/api/v1/decisions/sync", headers=headers, json={"document_id": str(document.id)})
    assert first_sync.status_code == 200
    first_items = first_sync.json()
    assert any(item["category"] == "core_gameplay_loop" for item in first_items)

    second_sync = client.post("/api/v1/decisions/sync", headers=headers, json={"document_id": str(document.id)})
    assert second_sync.status_code == 200
    assert len(second_sync.json()) == len(first_items)

    target = next(item for item in first_items if item["category"] == "core_gameplay_loop")
    resolved = client.put(
        f"/api/v1/decisions/{target['id']}",
        headers=headers,
        json={"decision": "Explore rooms, solve one puzzle, unlock the next room.", "status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert "Explore rooms" in resolved.json()["decision"]


def test_design_decisions_enforce_project_scope(db_session):
    owner_project = f"decision_owner_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="private_decision_source.md",
        file_bytes=b"A small private design source.",
        content_type="text/plain",
        game_project_id=owner_project,
    )

    response = client.post(
        "/api/v1/decisions/sync",
        headers={"X-Game-Project-ID": "not_the_owner"},
        json={"document_id": str(document.id)},
    )
    assert response.status_code == 404


def test_decision_coverage_uses_latest_source_revision(db_session):
    project_id = f"decision_coverage_{uuid.uuid4().hex[:8]}"
    rag = RAGService()
    original = rag.process_document(
        db=db_session,
        file_name="prototype_v1.md",
        file_bytes=b"A compact puzzle adventure.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    headers = {"X-Game-Project-ID": project_id}
    decisions = client.post("/api/v1/decisions/sync", headers=headers, json={"document_id": str(original.id)}).json()
    core_loop = next(item for item in decisions if item["category"] == "core_gameplay_loop")
    client.put(
        f"/api/v1/decisions/{core_loop['id']}",
        headers=headers,
        json={"decision": "Explore rooms, solve puzzles, unlock the next area.", "status": "resolved"},
    )

    revised = rag.process_document(
        db=db_session,
        file_name="prototype_v2.md",
        file_bytes=b"# Core loop\nExplore rooms, solve puzzles, and unlock the next area.",
        content_type="text/markdown",
        game_project_id=project_id,
        source_document=original,
    )
    response = client.get(f"/api/v1/decisions/coverage?document_id={revised.id}", headers=headers)

    assert response.status_code == 200
    coverage = response.json()
    core_loop_coverage = next(item for item in coverage["items"] if item["title"] == "Core gameplay loop")
    assert core_loop_coverage["evidence_status"] == "source_backed"
    assert core_loop_coverage["origin_revision_number"] == 1


def test_synced_decisions_keep_review_priority_and_recommended_source_kind(db_session):
    project_id = f"decision_metadata_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="delivery_scope.md",
        file_bytes=(
            b"# Project\n"
            b"The PC game includes an Android AR companion and an online leaderboard.\n"
            b"A story scene includes a suspicious server label.\n"
        ),
        content_type="text/markdown",
        game_project_id=project_id,
    )
    headers = {"X-Game-Project-ID": project_id}

    response = client.post(
        "/api/v1/decisions/sync",
        headers=headers,
        json={"document_id": str(document.id)},
    )

    assert response.status_code == 200
    decisions = {decision["title"]: decision for decision in response.json()}
    assert decisions["Multi-platform delivery scope"]["priority"] == "high"
    assert decisions["Multi-platform delivery scope"]["recommended_source_kind"] == "technical_brief"
    assert decisions["Online feature boundary"]["priority"] == "high"
    assert decisions["Online feature boundary"]["recommended_source_kind"] == "technical_brief"
