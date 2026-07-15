"""link decisions to supporting evidence documents

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-15 00:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("design_decisions", sa.Column("evidence_document_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_design_decisions_evidence_document_id_documents",
        "design_decisions",
        "documents",
        ["evidence_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_design_decisions_evidence_document_id", "design_decisions", ["evidence_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_design_decisions_evidence_document_id", table_name="design_decisions")
    op.drop_constraint("fk_design_decisions_evidence_document_id_documents", "design_decisions", type_="foreignkey")
    op.drop_column("design_decisions", "evidence_document_id")
