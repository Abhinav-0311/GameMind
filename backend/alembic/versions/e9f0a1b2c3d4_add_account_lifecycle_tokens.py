"""add account lifecycle tokens

Revision ID: e9f0a1b2c3d4
Revises: d8f1c3a5e762
Create Date: 2026-07-18 17:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d8f1c3a5e762"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("session_version", sa.Integer(), server_default="1", nullable=False))
    op.create_table(
        "account_action_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("game_project_id", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["game_project_id"], ["game_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    for column in ("token_hash", "purpose", "email", "user_id", "game_project_id", "expires_at"):
        op.create_index(f"ix_account_action_tokens_{column}", "account_action_tokens", [column], unique=False)


def downgrade() -> None:
    for column in ("expires_at", "game_project_id", "user_id", "email", "purpose", "token_hash"):
        op.drop_index(f"ix_account_action_tokens_{column}", table_name="account_action_tokens")
    op.drop_table("account_action_tokens")
    op.drop_column("users", "session_version")
    op.drop_column("users", "email_verified")
