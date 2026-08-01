from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.design_agent.contracts import ResumeDecision
from app.design_agent import jobs as jobs_module
from app.design_agent.jobs import DesignAgentJobService
from app.design_agent.provider import MockDesignAgentProvider
from app.design_agent.workflow import DesignAgentWorkflow
from app.models.design_agent import DesignAgentArtifact, DesignAgentJob, DesignAgentRun
from main import app
from test_design_agent_workflow import CountingRAG, create_source


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_job_queue(db_session):
    db_session.query(DesignAgentJob).delete()
    db_session.commit()
    yield
    db_session.query(DesignAgentJob).delete()
    db_session.commit()


class SuccessfulWorkflow:
    def __init__(self, *, session_factory, **_kwargs):
        self.session_factory = session_factory

    def start(self, run):
        with self.session_factory() as db:
            persisted = db.get(DesignAgentRun, run.id)
            persisted.status = "awaiting_review"
            persisted.current_node = "human_review"
            db.commit()

    def resume(self, run_id, decision):
        with self.session_factory() as db:
            persisted = db.get(DesignAgentRun, run_id)
            persisted.status = "completed" if decision.decision == "approve" else "awaiting_review"
            db.commit()


class FailingWorkflow(SuccessfulWorkflow):
    def start(self, run):
        raise RuntimeError("hosted provider unavailable")


def _factory(db_session):
    return sessionmaker(bind=db_session.get_bind(), autocommit=False, autoflush=False)


def _run(db_session, project_id="queue_project"):
    run = DesignAgentRun(
        game_project_id=project_id,
        objective="Build a durable queued workflow.",
        document_ids=[],
        provider_name="mock",
        model_config={},
    )
    db_session.add(run)
    db_session.flush()
    return run


def test_worker_claims_and_completes_start_job(db_session, monkeypatch):
    monkeypatch.setattr(jobs_module, "DesignAgentWorkflow", SuccessfulWorkflow)
    monkeypatch.setattr(jobs_module, "build_design_agent_provider", lambda: object())
    run = _run(db_session)
    job = DesignAgentJobService.enqueue_start(db_session, run)
    db_session.commit()
    job_id = job.id

    service = DesignAgentJobService(_factory(db_session))
    assert service.process_one("worker-test") is True

    db_session.expire_all()
    persisted_job = db_session.get(DesignAgentJob, job_id)
    persisted_run = db_session.get(DesignAgentRun, run.id)
    assert persisted_job.status == "succeeded"
    assert persisted_job.attempts == 1
    assert persisted_job.locked_by is None
    assert persisted_run.status == "awaiting_review"


def test_run_creation_transactionally_enqueues_in_queued_mode(db_session, monkeypatch):
    project_id = f"queued_api_{uuid.uuid4().hex[:8]}"
    document, _chunks = create_source(db_session, project_id)
    monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "queued")

    response = client.post(
        "/api/v1/design-agent/runs",
        headers={"X-Game-Project-ID": project_id},
        json={
            "objective": "Generate a durable queued game design blueprint.",
            "document_ids": [str(document.id)],
            "max_revisions": 2,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"
    run_id = uuid.UUID(response.json()["id"])
    job = db_session.query(DesignAgentJob).filter_by(run_id=run_id).one()
    assert job.operation == "start"
    assert job.game_project_id == project_id
    assert job.idempotency_key == f"start:{run_id}"


def test_stale_lease_is_reclaimed(db_session):
    run = _run(db_session, "lease_project")
    job = DesignAgentJobService.enqueue_start(db_session, run)
    job.status = "running"
    job.locked_by = "dead-worker"
    job.locked_at = datetime.now(timezone.utc) - timedelta(
        seconds=settings.DESIGN_AGENT_JOB_LEASE_SECONDS + 1
    )
    db_session.commit()

    claimed = DesignAgentJobService(_factory(db_session)).claim_next("replacement-worker")

    db_session.expire_all()
    persisted = db_session.get(DesignAgentJob, job.id)
    assert claimed == job.id
    assert persisted.locked_by == "replacement-worker"
    assert persisted.attempts == 1


def test_only_one_pending_job_is_claimed(db_session):
    first = _run(db_session, "isolation_a")
    second = _run(db_session, "isolation_b")
    first_job = DesignAgentJobService.enqueue_start(db_session, first)
    second_job = DesignAgentJobService.enqueue_start(db_session, second)
    db_session.commit()

    service = DesignAgentJobService(_factory(db_session))
    claimed = service.claim_next("worker-one")

    db_session.expire_all()
    statuses = {
        first_job.id: db_session.get(DesignAgentJob, first_job.id).status,
        second_job.id: db_session.get(DesignAgentJob, second_job.id).status,
    }
    assert statuses[claimed] == "running"
    assert list(statuses.values()).count("pending") == 1


def test_worker_that_lost_its_lease_cannot_overwrite_new_owner(db_session):
    run = _run(db_session, "lease_owner_project")
    job = DesignAgentJobService.enqueue_start(db_session, run)
    job.status = "running"
    job.locked_by = "replacement-worker"
    job.attempts = 2
    db_session.commit()

    service = DesignAgentJobService(_factory(db_session))
    service._record_failure(job.id, "stale-worker", "late provider failure")

    db_session.expire_all()
    persisted = db_session.get(DesignAgentJob, job.id)
    assert persisted.status == "running"
    assert persisted.locked_by == "replacement-worker"
    assert persisted.last_error is None


def test_terminal_failure_is_bounded_and_visible(db_session, monkeypatch):
    monkeypatch.setattr(jobs_module, "DesignAgentWorkflow", FailingWorkflow)
    monkeypatch.setattr(jobs_module, "build_design_agent_provider", lambda: object())
    run = _run(db_session, "failure_project")
    job = DesignAgentJobService.enqueue_start(db_session, run)
    job.max_attempts = 1
    db_session.commit()

    assert DesignAgentJobService(_factory(db_session)).process_one("worker-failure") is True

    db_session.expire_all()
    persisted_job = db_session.get(DesignAgentJob, job.id)
    persisted_run = db_session.get(DesignAgentRun, run.id)
    assert persisted_job.status == "failed"
    assert persisted_job.attempts == 1
    assert "hosted provider unavailable" in persisted_job.last_error
    assert persisted_run.status == "failed"


def test_real_graph_rejection_cycle_runs_through_queue_and_reuses_evidence(db_session):
    project_id = f"queued_graph_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rag = CountingRAG(chunks)
    factory = _factory(db_session)
    service = DesignAgentJobService(
        factory,
        workflow_factory=lambda session_factory: DesignAgentWorkflow(
            database_url=settings.DATABASE_URL,
            session_factory=session_factory,
            provider=MockDesignAgentProvider(),
            rag_service=rag,
        ),
    )
    run = DesignAgentRun(
        game_project_id=project_id,
        objective="Generate a cited, reviewable game design blueprint.",
        document_ids=[str(document.id)],
        provider_name="mock",
        model_config={},
        max_revisions=2,
    )
    db_session.add(run)
    db_session.flush()
    DesignAgentJobService.enqueue_start(db_session, run)
    db_session.commit()

    assert service.process_one("graph-worker") is True
    db_session.expire_all()
    run = db_session.get(DesignAgentRun, run.id)
    assert run.status == "awaiting_review"
    assert rag.calls == 1

    artifact = db_session.query(DesignAgentArtifact).filter_by(run_id=run.id).order_by(
        DesignAgentArtifact.version.desc()
    ).first()
    DesignAgentJobService.enqueue_resume(
        db_session,
        run,
        ResumeDecision(decision="reject", reason="Add Level 10: Incident Response."),
        artifact.id,
    )
    db_session.commit()
    assert service.process_one("graph-worker") is True

    db_session.expire_all()
    run = db_session.get(DesignAgentRun, run.id)
    assert run.status == "awaiting_review"
    assert run.revision_count == 1
    assert rag.calls == 1

    artifact = db_session.query(DesignAgentArtifact).filter_by(run_id=run.id).order_by(
        DesignAgentArtifact.version.desc()
    ).first()
    DesignAgentJobService.enqueue_resume(
        db_session,
        run,
        ResumeDecision(decision="approve"),
        artifact.id,
    )
    db_session.commit()
    assert service.process_one("graph-worker") is True

    db_session.expire_all()
    run = db_session.get(DesignAgentRun, run.id)
    assert run.status == "completed"
    assert rag.calls == 1
