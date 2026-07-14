import uuid

from fastapi.testclient import TestClient

from app.services.rag_service import RAGService
from main import app


client = TestClient(app)


def test_gdd_review_returns_missing_decisions_and_explicit_conflicts(db_session):
    project_id = f"review_project_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="scope_review.md",
        file_bytes=(
            b"# Prototype\n"
            b"A single-player puzzle adventure with online co-op planned at launch.\n"
            b"# Quest\nObjective: Restore the observatory beacon. Reward: access to the north tower."
        ),
        content_type="text/markdown",
        game_project_id=project_id,
    )

    response = client.get(
        f"/api/v1/reviews/documents/{document.id}",
        headers={"X-Game-Project-ID": project_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == str(document.id)
    assert data["summary"]["conflicts"] == 1
    findings = {finding["title"]: finding for finding in data["findings"]}
    assert findings["Player-mode conflict"]["severity"] == "conflict"
    assert findings["Core gameplay loop"]["severity"] == "needs_decision"
    assert findings["Quest or objective design"]["severity"] == "covered"


def test_gdd_review_enforces_project_scope(db_session):
    owner_project = f"review_owner_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="private_source.md",
        file_bytes=b"A private design document.",
        content_type="text/plain",
        game_project_id=owner_project,
    )

    response = client.get(
        f"/api/v1/reviews/documents/{document.id}",
        headers={"X-Game-Project-ID": "another_project"},
    )

    assert response.status_code == 404


def test_gdd_review_prioritizes_delivery_scope_and_recommends_a_supporting_source(db_session):
    project_id = f"delivery_scope_{uuid.uuid4().hex[:8]}"
    document = RAGService().process_document(
        db=db_session,
        file_name="cross_platform_game.md",
        file_bytes=(
            b"# Project plan\n"
            b"The PC game includes an Android AR companion and optional VR challenge levels.\n"
            b"A weekly online leaderboard rewards the fastest players."
        ),
        content_type="text/markdown",
        game_project_id=project_id,
    )

    response = client.get(
        f"/api/v1/reviews/documents/{document.id}",
        headers={"X-Game-Project-ID": project_id},
    )

    assert response.status_code == 200
    findings = {finding["title"]: finding for finding in response.json()["findings"]}
    assert findings["Multi-platform delivery scope"]["priority"] == "high"
    assert findings["Multi-platform delivery scope"]["recommended_source_kind"] == "technical_brief"
    assert findings["Online feature boundary"]["priority"] == "high"
