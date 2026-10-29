"""Durable Gemini daily reservations and per-run cap (no historical backfill)."""
import sqlalchemy as sa
from alembic import op

revision = "e3f5a7b9c012"
down_revision = "d2e4f6a8b901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("gemini_daily_usage",
        sa.Column("model_id", sa.String(255), primary_key=True),
        sa.Column("pacific_day", sa.Date(), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exhausted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("requests >= 0", name="ck_gemini_usage_nonnegative"))
    op.add_column("design_agent_runs", sa.Column("gemini_request_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("design_agent_runs", "gemini_request_count")
    op.drop_table("gemini_daily_usage")
