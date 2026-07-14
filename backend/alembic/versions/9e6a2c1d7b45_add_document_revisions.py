"""add document revisions

Revision ID: 9e6a2c1d7b45
Revises: 4a8c2e6f9b31
Create Date: 2026-07-14 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "9e6a2c1d7b45"
down_revision: Union[str, None] = "4a8c2e6f9b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_document_id", sa.UUID(), nullable=True))
    op.add_column("documents", sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False))
    op.create_foreign_key("fk_documents_source_document", "documents", "documents", ["source_document_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_documents_source_document_id", "documents", ["source_document_id"], unique=False)
    op.execute("UPDATE documents SET source_document_id = id WHERE source_document_id IS NULL")


def downgrade() -> None:
    op.drop_index("ix_documents_source_document_id", table_name="documents")
    op.drop_constraint("fk_documents_source_document", "documents", type_="foreignkey")
    op.drop_column("documents", "revision_number")
    op.drop_column("documents", "source_document_id")
