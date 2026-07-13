"""add blueprint gameplay systems

Revision ID: 319c4b1f0d7a
Revises: 655148f8d099
Create Date: 2026-07-13 18:15:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "319c4b1f0d7a"
down_revision: Union[str, None] = "655148f8d099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_blueprints",
        sa.Column("gameplay_systems", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_blueprints", "gameplay_systems")
