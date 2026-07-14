"""add document content hash

Revision ID: 7f2a9c8d1e4b
Revises: 319c4b1f0d7a
Create Date: 2026-07-14 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "7f2a9c8d1e4b"
down_revision: Union[str, None] = "319c4b1f0d7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_documents_project_content_hash",
        "documents",
        ["game_project_id", "content_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_project_content_hash", table_name="documents")
    op.drop_column("documents", "content_hash")
