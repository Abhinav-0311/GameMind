"""decouple_overrides

Revision ID: b733cf0567e9
Revises: 585f2df93d8f
Create Date: 2026-06-18 15:29:21.872607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b733cf0567e9'
down_revision: Union[str, None] = '585f2df93d8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    # Drop foreign key constraint that causes cascading deletes
    op.drop_constraint('consistency_overrides_validation_id_fkey', 'consistency_overrides', type_='foreignkey')
    
    # Add new auditing columns to preserve historical blocked data
    op.add_column('consistency_overrides', sa.Column('blocked_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('consistency_overrides', sa.Column('reason_blocked', sa.Text(), nullable=True))
    
    # Create index on validation_id for fast lookup/auditing
    op.create_index('ix_consistency_overrides_validation_id', 'consistency_overrides', ['validation_id'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_consistency_overrides_validation_id', table_name='consistency_overrides')
    
    # Drop auditing columns
    op.drop_column('consistency_overrides', 'reason_blocked')
    op.drop_column('consistency_overrides', 'blocked_payload')
    
    # Re-create the foreign key constraint with ON DELETE CASCADE
    op.create_foreign_key(
        'consistency_overrides_validation_id_fkey',
        'consistency_overrides',
        'pending_ingests',
        ['validation_id'],
        ['validation_id'],
        ondelete='CASCADE'
    )
