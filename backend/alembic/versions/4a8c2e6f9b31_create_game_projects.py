"""create game projects

Revision ID: 4a8c2e6f9b31
Revises: 7f2a9c8d1e4b
Create Date: 2026-07-14 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4a8c2e6f9b31"
down_revision: Union[str, None] = "7f2a9c8d1e4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_projects",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO game_projects (id, name) VALUES ('default_project', 'My first game') "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("game_projects")
