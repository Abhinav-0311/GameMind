"""add blueprint source documents

Revision ID: f6c2e9a4d830
Revises: e5b1d8c3f729
Create Date: 2026-07-14 19:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f6c2e9a4d830"
down_revision: Union[str, None] = "e5b1d8c3f729"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_blueprints",
        sa.Column("source_document_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.execute("UPDATE game_blueprints SET source_document_ids = jsonb_build_array(document_id::text) WHERE document_id IS NOT NULL AND source_document_ids = '[]'::jsonb")


def downgrade() -> None:
    op.drop_column("game_blueprints", "source_document_ids")
