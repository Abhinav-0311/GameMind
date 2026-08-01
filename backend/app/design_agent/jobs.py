"""Durable PostgreSQL execution queue for design-agent graph operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from threading import Event, Thread
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.design_agent.contracts import ResumeDecision
from app.design_agent.provider_factory import build_design_agent_provider
from app.design_agent.workflow import DesignAgentWorkflow
from app.models.design_agent import DesignAgentJob, DesignAgentRun


logger = logging.getLogger("gamemind.design_agent_jobs")


class DesignAgentJobService:
    def __init__(
        self,
        session_factory: sessionmaker,
        workflow_factory: Callable[[sessionmaker], DesignAgentWorkflow] | None = None,
    ):
        self.session_factory = session_factory
        self.workflow_factory = workflow_factory

    @staticmethod
    def enqueue_start(db: Session, run: DesignAgentRun) -> DesignAgentJob:
        job = DesignAgentJob(
            run_id=run.id,
            game_project_id=run.game_project_id,
            operation="start",
            idempotency_key=f"start:{run.id}",
            max_attempts=settings.DESIGN_AGENT_JOB_MAX_ATTEMPTS,
        )
        run.status = "queued"
        db.add(job)
        return job

    @staticmethod
    def enqueue_resume(
        db: Session,
        run: DesignAgentRun,
        decision: ResumeDecision,
        artifact_id: UUID,
    ) -> DesignAgentJob:
        job = DesignAgentJob(
            run_id=run.id,
            game_project_id=run.game_project_id,
            operation="resume",
            payload=decision.model_dump(mode="json"),
            idempotency_key=f"resume:{run.id}:{artifact_id}",
            max_attempts=settings.DESIGN_AGENT_JOB_MAX_ATTEMPTS,
        )
        run.status = "review_queued"
        db.add(job)
        return job

    def claim_next(self, worker_id: str) -> UUID | None:
        now = datetime.now(timezone.utc)
        lease_cutoff = now - timedelta(seconds=settings.DESIGN_AGENT_JOB_LEASE_SECONDS)
        with self.session_factory() as db:
            reclaimed = db.query(DesignAgentJob).filter(
                DesignAgentJob.status == "running",
                DesignAgentJob.locked_at < lease_cutoff,
            ).update(
                {
                    DesignAgentJob.status: "pending",
                    DesignAgentJob.locked_at: None,
                    DesignAgentJob.locked_by: None,
                },
                synchronize_session=False,
            )
            if reclaimed:
                db.flush()

            job = db.query(DesignAgentJob).filter(
                DesignAgentJob.status == "pending",
                DesignAgentJob.available_at <= now,
            ).order_by(DesignAgentJob.created_at).with_for_update(skip_locked=True).first()
            if job is None:
                db.commit()
                return None
            job.status = "running"
            job.attempts += 1
            job.locked_at = now
            job.locked_by = worker_id
            db.commit()
            return job.id

    def execute(self, job_id: UUID) -> None:
        with self.session_factory() as db:
            job = db.get(DesignAgentJob, job_id)
            if job is None or job.status != "running":
                return
            run = db.get(DesignAgentRun, job.run_id)
            if run is None:
                job.status = "failed"
                job.last_error = "Design-agent run no longer exists."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
            operation = job.operation
            payload = dict(job.payload or {})
            run_id = run.id
            worker_id = job.locked_by

        workflow = (
            self.workflow_factory(self.session_factory)
            if self.workflow_factory
            else DesignAgentWorkflow(
                database_url=settings.DATABASE_URL,
                session_factory=self.session_factory,
                provider=build_design_agent_provider(),
            )
        )
        heartbeat_stop = Event()
        heartbeat = Thread(
            target=self._heartbeat,
            args=(job_id, worker_id, heartbeat_stop),
            daemon=True,
        )
        heartbeat.start()
        try:
            if operation == "start":
                with self.session_factory() as db:
                    run = db.get(DesignAgentRun, run_id)
                    workflow.start(run)
            elif operation == "resume":
                workflow.resume(run_id, ResumeDecision.model_validate(payload))
            else:
                raise ValueError(f"Unsupported design-agent job operation: {operation}")
        except Exception as error:
            self._record_failure(job_id, worker_id, str(error))
            return
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=2)

        with self.session_factory() as db:
            job = db.query(DesignAgentJob).filter(
                DesignAgentJob.id == job_id,
                DesignAgentJob.status == "running",
                DesignAgentJob.locked_by == worker_id,
            ).first()
            if job is None:
                logger.warning("Design-agent job %s completed after its lease was lost", job_id)
                return
            job.status = "succeeded"
            job.locked_at = None
            job.locked_by = None
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        logger.info("Design-agent job %s succeeded", job_id)

    def _heartbeat(self, job_id: UUID, worker_id: str | None, stop: Event) -> None:
        interval = max(5.0, settings.DESIGN_AGENT_JOB_LEASE_SECONDS / 3)
        while not stop.wait(interval):
            with self.session_factory() as db:
                job = db.get(DesignAgentJob, job_id)
                if job is None or job.status != "running" or job.locked_by != worker_id:
                    return
                job.locked_at = datetime.now(timezone.utc)
                db.commit()

    def _record_failure(self, job_id: UUID, worker_id: str | None, error: str) -> None:
        with self.session_factory() as db:
            job = db.query(DesignAgentJob).filter(
                DesignAgentJob.id == job_id,
                DesignAgentJob.status == "running",
                DesignAgentJob.locked_by == worker_id,
            ).first()
            if job is None:
                logger.warning("Design-agent job %s failed after its lease was lost", job_id)
                return
            run = db.get(DesignAgentRun, job.run_id)
            job.last_error = error[:4000]
            job.locked_at = None
            job.locked_by = None
            if job.attempts < job.max_attempts:
                job.status = "pending"
                job.available_at = datetime.now(timezone.utc) + timedelta(
                    seconds=min(30, 2 ** job.attempts)
                )
                if run:
                    run.status = "queued" if job.operation == "start" else "review_queued"
            else:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                if run:
                    run.status = "failed"
                    run.last_error = error[:4000]
            db.commit()
        logger.warning("Design-agent job %s failed: %s", job_id, error)

    def process_one(self, worker_id: str) -> bool:
        job_id = self.claim_next(worker_id)
        if job_id is None:
            return False
        logger.info("Design-agent worker %s claimed job %s", worker_id, job_id)
        self.execute(job_id)
        return True
