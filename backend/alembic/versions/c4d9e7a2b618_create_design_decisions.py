"""create design decisions

Revision ID: c4d9e7a2b618
Revises: 9e6a2c1d7b45
Create Date: 2026-07-14 17:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4d9e7a2b618"
down_revision: Union[str, None] = "9e6a2c1d7b45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "design_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("game_project_id", sa.String(length=100), nullable=False, server_default="default_project"),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=30), nullable=False, server_default="needs_decision"),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_project_id", "document_id", "category", name="uq_design_decisions_project_document_category"),
    )
    op.create_index("ix_design_decisions_game_project_id", "design_decisions", ["game_project_id"], unique=False)
    op.create_index("ix_design_decisions_document_id", "design_decisions", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_design_decisions_document_id", table_name="design_decisions")
    op.drop_index("ix_design_decisions_game_project_id", table_name="design_decisions")
    op.drop_table("design_decisions")
