import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.v1.design_agent import get_design_agent_service
from app.config import settings
from app.design_agent.provider import MockDesignAgentProvider
from app.design_agent.service import DesignAgentService
from app.design_agent.workflow import DesignAgentWorkflow
from app.models.blueprint import GameBlueprint
from app.models.design_agent import (
    DesignAgentArtifact,
    DesignAgentEvidenceSnapshot,
    DesignAgentReviewEvent,
    DesignAgentRun,
)
from app.models.document import Document, DocumentChunk
from main import app

client = TestClient(app)


class CountingRAG:
    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks
        self.calls = 0
        self.requests = []

    def query_lore(
        self,
        query_text: str,
        limit: int = 5,
        game_project_id: str = "default_project",
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        self.calls += 1
        self.requests.append(
            {
                "query_text": query_text,
                "limit": limit,
                "game_project_id": game_project_id,
                "document_ids": document_ids,
            }
        )
        allowed = set(document_ids or [])
        return [
            {
                "chunk_id": str(chunk.id),
                "content": chunk.content,
                "document_id": str(chunk.document_id),
                "title": chunk.document.title,
                "chunk_index": chunk.chunk_index,
                "similarity": 0.91,
                "confidence": "High",
            }
            for chunk in self.chunks
            if not allowed or str(chunk.document_id) in allowed
        ][:limit]


def create_source(db_session, game_project_id: str) -> tuple[Document, list[DocumentChunk]]:
    document = Document(
        title="Reference Game Design Document.md",
        content_type="text/markdown",
        source_kind="gdd",
        game_project_id=game_project_id,
    )
    db_session.add(document)
    db_session.flush()
    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content=(
                "The player defends a digital city through nine security missions. "
                "Level progression introduces reconnaissance, phishing defense, and incident response."
            ),
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=1,
            content=(
                "Mentor NPCs explain evidence-backed cybersecurity choices. "
                "Quest outcomes change trust and unlock the final investigation."
            ),
        ),
    ]
    db_session.add_all(chunks)
    db_session.commit()
    db_session.refresh(document)
    return document, chunks


def make_service(db_session, rag: CountingRAG) -> DesignAgentService:
    factory = sessionmaker(
        bind=db_session.get_bind(),
        autocommit=False,
        autoflush=False,
    )
    return DesignAgentService(
        DesignAgentWorkflow(
            database_url=settings.DATABASE_URL,
            session_factory=factory,
            provider=MockDesignAgentProvider(),
            rag_service=rag,
        )
    )


def start_run(service: DesignAgentService, document_id: uuid.UUID, game_project_id: str):
    app.dependency_overrides[get_design_agent_service] = lambda: service
    response = client.post(
        "/api/v1/design-agent/runs",
        headers={"X-Game-Project-ID": game_project_id},
        json={
            "objective": "Generate a cited, reviewable game design blueprint.",
            "document_ids": [str(document_id)],
            "max_revisions": 2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_run_pauses_with_durable_checkpoint_and_trace(db_session):
    project_id = f"agent_trace_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rag = CountingRAG(chunks)
    service = make_service(db_session, rag)

    try:
        run = start_run(service, document.id, project_id)
        assert run["status"] == "awaiting_review"
        assert run["current_node"] == "human_review"
        assert run["retrieval_revision"] == 1
        assert run["current_artifact"]["artifact_type"] == "draft"
        assert run["critique"]["content"]["findings"]
        assert rag.calls == 1

        trace_response = client.get(
            f"/api/v1/design-agent/runs/{run['id']}/trace",
            headers={"X-Game-Project-ID": project_id},
        )
        assert trace_response.status_code == 200
        trace = trace_response.json()["items"]
        assert [item["node_name"] for item in trace[:5]] == [
            "plan",
            "retrieve_evidence",
            "generate_blueprint",
            "critique",
            "human_review",
        ]
        assert trace[-1]["status"] == "waiting"
        assert all(item["cost_usd"] == 0 for item in trace)

        checkpoint_count = db_session.execute(
            __import__("sqlalchemy").text(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = :thread_id"
            ),
            {"thread_id": f"design-agent:{run['id']}"},
        ).scalar()
        assert checkpoint_count > 0
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_rejection_reuses_evidence_and_restart_resume_completes(db_session):
    project_id = f"agent_resume_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rag = CountingRAG(chunks)
    first_service = make_service(db_session, rag)

    try:
        run = start_run(first_service, document.id, project_id)
        run_id = run["id"]
        first_snapshot_id = db_session.query(DesignAgentEvidenceSnapshot.id).filter(
            DesignAgentEvidenceSnapshot.run_id == uuid.UUID(run_id)
        ).scalar()

        rejection = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={
                "decision": "reject",
                "reason": "The level design is inaccurate; preserve the evidence and correct the level section.",
            },
        )
        assert rejection.status_code == 200, rejection.text
        revised = rejection.json()
        assert revised["status"] == "awaiting_review"
        assert revised["revision_count"] == 1
        assert revised["current_artifact"]["artifact_type"] == "revision"
        assert (
            revised["current_artifact"]["content"]["level_design_suggestions"]["content"]["human_revision"]
            == "The level design is inaccurate; preserve the evidence and correct the level section."
        )
        assert rag.calls == 1
        assert db_session.query(DesignAgentEvidenceSnapshot).filter(
            DesignAgentEvidenceSnapshot.run_id == uuid.UUID(run_id)
        ).count() == 1
        assert db_session.query(DesignAgentEvidenceSnapshot.id).filter(
            DesignAgentEvidenceSnapshot.run_id == uuid.UUID(run_id)
        ).scalar() == first_snapshot_id

        # A new workflow/service object simulates an application restart. It has
        # no in-memory graph state and must resume from PostgreSQL.
        restarted_service = make_service(db_session, rag)
        app.dependency_overrides[get_design_agent_service] = lambda: restarted_service
        approval = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "approve"},
        )
        assert approval.status_code == 200, approval.text
        completed = approval.json()
        assert completed["status"] == "completed"
        assert completed["current_artifact"]["artifact_type"] == "final"
        assert completed["current_artifact"]["immutable"] is True
        assert completed["current_artifact"]["blueprint_id"]
        assert rag.calls == 1

        blueprint = db_session.query(GameBlueprint).filter(
            GameBlueprint.id == uuid.UUID(completed["current_artifact"]["blueprint_id"])
        ).one()
        assert blueprint.status == "approved"

        brief = client.get(
            f"/api/v1/design-agent/runs/{run_id}/exports/technical-brief",
            headers={"X-Game-Project-ID": project_id},
        )
        assert brief.status_code == 200
        assert "# Agent Blueprint:" in brief.text
        assert "## Sources" in brief.text

        runtime = client.get(
            f"/api/v1/design-agent/runs/{run_id}/exports/runtime",
            headers={"X-Game-Project-ID": project_id},
        )
        assert runtime.status_code == 200
        assert runtime.json()["runtime_data"]["generation_mode"] == "mock"

        duplicate_review = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "approve"},
        )
        assert duplicate_review.status_code == 409
        assert db_session.query(DesignAgentArtifact).filter(
            DesignAgentArtifact.run_id == uuid.UUID(run_id),
            DesignAgentArtifact.artifact_type == "final",
        ).count() == 1
        assert db_session.query(DesignAgentReviewEvent).filter(
            DesignAgentReviewEvent.run_id == uuid.UUID(run_id)
        ).count() == 2
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_run_is_project_scoped_and_rejection_requires_reason(db_session):
    project_id = f"agent_scope_{uuid.uuid4().hex[:8]}"
    other_project_id = f"agent_other_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    service = make_service(db_session, CountingRAG(chunks))

    try:
        run = start_run(service, document.id, project_id)
        cross_project = client.get(
            f"/api/v1/design-agent/runs/{run['id']}",
            headers={"X-Game-Project-ID": other_project_id},
        )
        assert cross_project.status_code == 404

        invalid_rejection = client.post(
            f"/api/v1/design-agent/runs/{run['id']}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "reject", "reason": "   "},
        )
        assert invalid_rejection.status_code == 422

        export_before_approval = client.get(
            f"/api/v1/design-agent/runs/{run['id']}/exports/runtime",
            headers={"X-Game-Project-ID": project_id},
        )
        assert export_before_approval.status_code == 409
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
