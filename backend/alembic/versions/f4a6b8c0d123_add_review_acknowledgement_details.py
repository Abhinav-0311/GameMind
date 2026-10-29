"""Store explicit degraded-output approval acknowledgement, without historical backfill."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = 'f4a6b8c0d123'
down_revision = 'e3f5a7b9c012'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('design_agent_review_events', sa.Column('details', postgresql.JSONB(),
                  nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade():
    op.drop_column('design_agent_review_events', 'details')
