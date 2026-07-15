"""retain review priority and source recommendations on decisions

Revision ID: a1b2c3d4e5f6
Revises: f6c2e9a4d830
Create Date: 2026-07-15 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f6c2e9a4d830"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "design_decisions",
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
    )
    op.add_column(
        "design_decisions",
        sa.Column("recommended_source_kind", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("design_decisions", "recommended_source_kind")
    op.drop_column("design_decisions", "priority")
