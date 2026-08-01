import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.sql import func

from app.database import Base, ProjectScopedMixin


# LangGraph owns the contents of these tables. Declaring them in Base.metadata
# lets Alembic and clean-schema tests remain the authority for their structure.
checkpoint_migrations = Table(
    "checkpoint_migrations",
    Base.metadata,
    Column("v", Integer, primary_key=True),
)

checkpoints = Table(
    "checkpoints",
    Base.metadata,
    Column("thread_id", Text, primary_key=True),
    Column("checkpoint_ns", Text, primary_key=True, server_default=text("''")),
    Column("checkpoint_id", Text, primary_key=True),
    Column("parent_checkpoint_id", Text, nullable=True),
    Column("type", Text, nullable=True),
    Column("checkpoint", JSONB, nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Index("checkpoints_thread_id_idx", "thread_id"),
)

checkpoint_blobs = Table(
    "checkpoint_blobs",
    Base.metadata,
    Column("thread_id", Text, primary_key=True),
    Column("checkpoint_ns", Text, primary_key=True, server_default=text("''")),
    Column("channel", Text, primary_key=True),
    Column("version", Text, primary_key=True),
    Column("type", Text, nullable=False),
    Column("blob", BYTEA, nullable=True),
    Index("checkpoint_blobs_thread_id_idx", "thread_id"),
)

checkpoint_writes = Table(
    "checkpoint_writes",
    Base.metadata,
    Column("thread_id", Text, primary_key=True),
    Column("checkpoint_ns", Text, primary_key=True, server_default=text("''")),
    Column("checkpoint_id", Text, primary_key=True),
    Column("task_id", Text, primary_key=True),
    Column("idx", Integer, primary_key=True),
    Column("channel", Text, nullable=False),
    Column("type", Text, nullable=True),
    Column("blob", BYTEA, nullable=False),
    Column("task_path", Text, nullable=False, server_default=text("''")),
    Index("checkpoint_writes_thread_id_idx", "thread_id"),
)


class DesignAgentRun(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_runs"
    __table_args__ = (
        UniqueConstraint("game_project_id", "id", name="uq_design_agent_run_project_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    objective = Column(Text, nullable=False)
    document_ids = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    status = Column(String(32), nullable=False, default="created", server_default="created", index=True)
    current_node = Column(String(64), nullable=True)
    provider_name = Column(String(64), nullable=False, default="mock", server_default="mock")
    model_config = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    retrieval_revision = Column(Integer, nullable=False, default=0, server_default="0")
    revision_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_revisions = Column(Integer, nullable=False, default=2, server_default="2")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class DesignAgentJob(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_design_agent_job_idempotency_key"),
        Index("ix_design_agent_jobs_claim", "status", "available_at", "created_at"),
        ForeignKeyConstraint(
            ["game_project_id", "run_id"],
            ["design_agent_runs.game_project_id", "design_agent_runs.id"],
            name="fk_design_agent_job_project_run",
            ondelete="CASCADE",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    operation = Column(String(16), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    idempotency_key = Column(String(160), nullable=False)
    status = Column(String(24), nullable=False, default="pending", server_default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    available_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(120), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class DesignAgentEvidenceSnapshot(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_evidence_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "revision", name="uq_design_agent_evidence_run_revision"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    query = Column(Text, nullable=False)
    items = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DesignAgentArtifact(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_artifacts"
    __table_args__ = (
        UniqueConstraint("run_id", "version", name="uq_design_agent_artifact_run_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    blueprint_id = Column(
        UUID(as_uuid=True),
        ForeignKey("game_blueprints.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version = Column(Integer, nullable=False)
    artifact_type = Column(String(24), nullable=False, index=True)
    content = Column(JSONB, nullable=False)
    immutable = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DesignAgentCritique(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_critiques"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(JSONB, nullable=False)
    provider_name = Column(String(64), nullable=False)
    model_name = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DesignAgentReviewEvent(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_review_events"
    __table_args__ = (
        UniqueConstraint("artifact_id", name="uq_design_agent_review_artifact"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_label = Column(String(160), nullable=False, default="local_developer", server_default="local_developer")
    decision = Column(String(16), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DesignAgentNodeExecution(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_node_executions"
    __table_args__ = (
        UniqueConstraint("run_id", "node_name", "attempt", name="uq_design_agent_node_attempt"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_name = Column(String(64), nullable=False, index=True)
    attempt = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False, index=True)
    provider_name = Column(String(64), nullable=True)
    model_name = Column(String(128), nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0, server_default="0")
    input_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    output_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    cost_usd = Column(Numeric(12, 6), nullable=False, default=0, server_default="0")
    details = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class DesignAgentEvaluation(Base, ProjectScopedMixin):
    __tablename__ = "design_agent_evaluations"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_design_agent_evaluation_run"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("design_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluator_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evaluator_label = Column(
        String(160),
        nullable=False,
        default="local_developer",
        server_default="local_developer",
    )
    rubric_version = Column(String(32), nullable=False, default="cyberrakshak-v1", server_default="cyberrakshak-v1")
    annotations = Column(JSONB, nullable=False)
    metrics = Column(JSONB, nullable=False)
    overall_score = Column(Numeric(5, 4), nullable=False)
    passed = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
