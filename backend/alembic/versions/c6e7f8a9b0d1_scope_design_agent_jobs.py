"""enforce project-scoped design agent jobs

Revision ID: c6e7f8a9b0d1
Revises: b5d6e7f8a9c0
Create Date: 2026-08-01 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c6e7f8a9b0d1"
down_revision: Union[str, Sequence[str], None] = "b5d6e7f8a9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_design_agent_run_project_id",
        "design_agent_runs",
        ["game_project_id", "id"],
    )
    op.drop_constraint(
        "design_agent_jobs_run_id_fkey",
        "design_agent_jobs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_design_agent_job_project_run",
        "design_agent_jobs",
        "design_agent_runs",
        ["game_project_id", "run_id"],
        ["game_project_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_design_agent_job_project_run",
        "design_agent_jobs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "design_agent_jobs_run_id_fkey",
        "design_agent_jobs",
        "design_agent_runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "uq_design_agent_run_project_id",
        "design_agent_runs",
        type_="unique",
    )
