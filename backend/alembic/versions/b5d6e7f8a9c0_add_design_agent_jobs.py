"""add durable design agent jobs

Revision ID: b5d6e7f8a9c0
Revises: a4c5d6e7f8b9
Create Date: 2026-08-01 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b5d6e7f8a9c0"
down_revision: Union[str, Sequence[str], None] = "a4c5d6e7f8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "design_agent_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("game_project_id", sa.String(length=100), server_default="default_project", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["design_agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_design_agent_job_idempotency_key"),
    )
    op.create_index("ix_design_agent_jobs_run_id", "design_agent_jobs", ["run_id"])
    op.create_index("ix_design_agent_jobs_status", "design_agent_jobs", ["status"])
    op.create_index("ix_design_agent_jobs_game_project_id", "design_agent_jobs", ["game_project_id"])
    op.create_index(
        "ix_design_agent_jobs_claim",
        "design_agent_jobs",
        ["status", "available_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_design_agent_jobs_claim", table_name="design_agent_jobs")
    op.drop_index("ix_design_agent_jobs_game_project_id", table_name="design_agent_jobs")
    op.drop_index("ix_design_agent_jobs_status", table_name="design_agent_jobs")
    op.drop_index("ix_design_agent_jobs_run_id", table_name="design_agent_jobs")
    op.drop_table("design_agent_jobs")
