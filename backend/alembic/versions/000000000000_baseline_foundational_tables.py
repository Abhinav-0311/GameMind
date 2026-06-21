"""baseline foundational tables

Revision ID: 000000000000
Revises: 
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '000000000000'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Documents
    op.create_table(
        'documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'document_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. NPC Profiles
    op.create_table(
        'npc_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=True),
        sa.Column('personality_summary', sa.Text(), nullable=False),
        sa.Column('dialogue_style', sa.Text(), nullable=True),
        sa.Column('voice_profile', sa.String(length=100), nullable=True),
        sa.Column('faction_alignment', sa.String(length=100), nullable=True),
        sa.Column('animation_hints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('memory_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='npc_profiles_slug_key')
    )

    # 3. Quests
    op.create_table(
        'quests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('npc_slug', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('difficulty', sa.String(length=50), server_default='Medium', nullable=False),
        sa.Column('gold_reward', sa.Integer(), server_default='0', nullable=False),
        sa.Column('xp_reward', sa.Integer(), server_default='0', nullable=False),
        sa.Column('item_rewards', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['npc_slug'], ['npc_profiles.slug'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'quest_objectives',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('quest_id', sa.UUID(), nullable=False),
        sa.Column('objective_index', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=100), nullable=False),
        sa.Column('quantity_required', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['quest_id'], ['quests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'quest_progress',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('player_id', sa.String(length=100), server_default='default_player', nullable=False),
        sa.Column('quest_id', sa.UUID(), nullable=False),
        sa.Column('quest_giver_slug', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
        sa.Column('objectives_state', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['quest_giver_slug'], ['npc_profiles.slug'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['quest_id'], ['quests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'quest_id', name='uq_player_quest')
    )

    # 4. Conversations
    op.create_table(
        'conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('npc_id', sa.UUID(), nullable=False),
        sa.Column('npc_slug', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('conversation_summary', sa.Text(), nullable=True),
        sa.Column('last_summarized_message_id', sa.UUID(), nullable=True),
        sa.Column('summary_version', sa.Integer(), server_default='0', nullable=False),
        sa.Column('summary_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['npc_id'], ['npc_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 5. Messages
    op.create_table(
        'messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('sender', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Set up message link alter for conversations
    op.create_foreign_key(
        'fk_conversations_last_summarized_message',
        'conversations', 'messages',
        ['last_summarized_message_id'], ['id'],
        ondelete='SET NULL', use_alter=True
    )

    # 6. NPC Memories
    op.create_table(
        'npc_memories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('npc_id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=True),
        sa.Column('memory_text', sa.Text(), nullable=False),
        sa.Column('memory_type', sa.String(length=50), server_default='episodic', nullable=False),
        sa.Column('importance_score', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('chroma_indexed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('archived', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['npc_id'], ['npc_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. NPC Relationships
    op.create_table(
        'npc_relationships',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('player_id', sa.String(length=100), server_default='default_player', nullable=False),
        sa.Column('npc_slug', sa.String(length=100), nullable=False),
        sa.Column('trust', sa.Integer(), server_default='50', nullable=False),
        sa.Column('respect', sa.Integer(), server_default='50', nullable=False),
        sa.Column('friendship', sa.Integer(), server_default='50', nullable=False),
        sa.Column('fear', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_reason', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['npc_slug'], ['npc_profiles.slug'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'npc_slug', name='uq_player_npc')
    )

    # 8. World State Flags
    op.create_table(
        'world_state_flags',
        sa.Column('flag_key', sa.String(length=100), nullable=False),
        sa.Column('flag_value', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('flag_key')
    )

    # 9. Telemetry logs
    op.create_table(
        'llm_telemetry_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=True),
        sa.Column('action_type', sa.String(length=50), server_default='dialogue', nullable=False),
        sa.Column('npc_slug', sa.String(length=100), nullable=False),
        sa.Column('model_used', sa.String(length=100), nullable=False),
        sa.Column('llm_provider', sa.String(length=50), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('output_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('estimated_cost_usd', sa.Numeric(precision=12, scale=6), server_default='0.0', nullable=False),
        sa.Column('safety_blocked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('safety_ratings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_llm_telemetry_logs_action_type', 'llm_telemetry_logs', ['action_type'], unique=False)
    op.create_index('ix_llm_telemetry_logs_conversation_id', 'llm_telemetry_logs', ['conversation_id'], unique=False)
    op.create_index('ix_llm_telemetry_logs_created_at', 'llm_telemetry_logs', ['created_at'], unique=False)
    op.create_index('ix_llm_telemetry_logs_npc_slug', 'llm_telemetry_logs', ['npc_slug'], unique=False)


def downgrade() -> None:
    # Drop the messages constraints from conversations first
    op.drop_constraint('fk_conversations_last_summarized_message', 'conversations', type_='foreignkey')

    op.drop_index('ix_llm_telemetry_logs_npc_slug', table_name='llm_telemetry_logs')
    op.drop_index('ix_llm_telemetry_logs_created_at', table_name='llm_telemetry_logs')
    op.drop_index('ix_llm_telemetry_logs_conversation_id', table_name='llm_telemetry_logs')
    op.drop_index('ix_llm_telemetry_logs_action_type', table_name='llm_telemetry_logs')
    op.drop_table('llm_telemetry_logs')

    op.drop_table('world_state_flags')
    op.drop_table('npc_relationships')
    op.drop_table('npc_memories')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('quest_progress')
    op.drop_table('quest_objectives')
    op.drop_table('quests')
    op.drop_table('npc_profiles')
    op.drop_table('document_chunks')
    op.drop_table('documents')
