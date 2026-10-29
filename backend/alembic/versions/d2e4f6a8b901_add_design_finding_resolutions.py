"""Add evidence-linked human finding-review audit records (no approval override).

Revision ID: d2e4f6a8b901
Revises: c6e7f8a9b0d1
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d2e4f6a8b901"
down_revision = "c6e7f8a9b0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_design_agent_artifact_scope", "design_agent_artifacts", ["game_project_id", "run_id", "id"])
    op.create_unique_constraint("uq_design_agent_critique_scope", "design_agent_critiques", ["game_project_id", "run_id", "artifact_id", "id"])
    op.create_table(
        "design_agent_finding_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("game_project_id", sa.String(100), nullable=False, server_default="default_project"),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("critique_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("design_agent_evidence_snapshots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("critique_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("finding_id", sa.String(64), nullable=False),
        sa.Column("finding_index", sa.Integer(), nullable=False),
        sa.Column("finding_content", postgresql.JSONB(), nullable=False),
        sa.Column("disposition", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("artifact_value", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_chunk_id", sa.String(100), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewer_label", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("critique_id", "finding_id", name="uq_design_finding_resolution"),
        sa.CheckConstraint("disposition = 'not_a_defect'", name="ck_design_finding_disposition"),
        sa.ForeignKeyConstraint(
            ["game_project_id", "run_id", "artifact_id"],
            ["design_agent_artifacts.game_project_id", "design_agent_artifacts.run_id", "design_agent_artifacts.id"],
            name="fk_design_finding_artifact_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["game_project_id", "run_id", "artifact_id", "critique_id"],
            ["design_agent_critiques.game_project_id", "design_agent_critiques.run_id", "design_agent_critiques.artifact_id", "design_agent_critiques.id"],
            name="fk_design_finding_critique_scope", ondelete="CASCADE"),
    )
    for column in ("game_project_id", "run_id", "artifact_id"):
        op.create_index("ix_design_agent_finding_resolutions_" + column, "design_agent_finding_resolutions", [column])


def downgrade():
    op.drop_table("design_agent_finding_resolutions")
    op.drop_constraint("uq_design_agent_critique_scope", "design_agent_critiques", type_="unique")
    op.drop_constraint("uq_design_agent_artifact_scope", "design_agent_artifacts", type_="unique")
