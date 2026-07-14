"""add document source kind

Revision ID: e5b1d8c3f729
Revises: c4d9e7a2b618
Create Date: 2026-07-14 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5b1d8c3f729"
down_revision: Union[str, None] = "c4d9e7a2b618"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_kind", sa.String(length=40), nullable=False, server_default="general"))


def downgrade() -> None:
    op.drop_column("documents", "source_kind")
