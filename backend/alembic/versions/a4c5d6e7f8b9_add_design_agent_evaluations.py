"""add design agent evaluations

Revision ID: a4c5d6e7f8b9
Revises: f1a2b3c4d5e6
Create Date: 2026-07-29 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a4c5d6e7f8b9"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "design_agent_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluator_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "evaluator_label",
            sa.String(length=160),
            server_default="local_developer",
            nullable=False,
        ),
        sa.Column(
            "rubric_version",
            sa.String(length=32),
            server_default="cyberrakshak-v1",
            nullable=False,
        ),
        sa.Column("annotations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("overall_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("passed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "game_project_id",
            sa.String(length=100),
            server_default="default_project",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evaluator_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["design_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_design_agent_evaluation_run"),
    )
    op.create_index(
        "ix_design_agent_evaluations_run_id",
        "design_agent_evaluations",
        ["run_id"],
    )
    op.create_index(
        "ix_design_agent_evaluations_evaluator_user_id",
        "design_agent_evaluations",
        ["evaluator_user_id"],
    )
    op.create_index(
        "ix_design_agent_evaluations_passed",
        "design_agent_evaluations",
        ["passed"],
    )
    op.create_index(
        "ix_design_agent_evaluations_game_project_id",
        "design_agent_evaluations",
        ["game_project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_design_agent_evaluations_game_project_id",
        table_name="design_agent_evaluations",
    )
    op.drop_index(
        "ix_design_agent_evaluations_passed",
        table_name="design_agent_evaluations",
    )
    op.drop_index(
        "ix_design_agent_evaluations_evaluator_user_id",
        table_name="design_agent_evaluations",
    )
    op.drop_index(
        "ix_design_agent_evaluations_run_id",
        table_name="design_agent_evaluations",
    )
    op.drop_table("design_agent_evaluations")
