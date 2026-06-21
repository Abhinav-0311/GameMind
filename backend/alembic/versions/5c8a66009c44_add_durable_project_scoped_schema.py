"""add_durable_project_scoped_schema

Revision ID: 5c8a66009c44
Revises: cb61e6326352
Create Date: 2026-06-21 18:03:53.685720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c8a66009c44'
down_revision: Union[str, None] = 'cb61e6326352'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # 1. Inspect existing schema and add missing game_project_id columns
    tables_to_isolate = [
        "npc_profiles",
        "world_state_flags",
        "npc_relationships",
        "quests",
        "quest_progress",
        "generated_quests",
        "conversations",
        "npc_memories",
        "world_entities"
    ]
    
    for table in tables_to_isolate:
        columns = [c['name'] for c in inspector.get_columns(table)]
        if 'game_project_id' not in columns:
            # Add column as nullable first
            op.add_column(table, sa.Column('game_project_id', sa.String(length=100), nullable=True))
            
    # 2. Backfill with 'default_project'
    for table in tables_to_isolate:
        op.execute(f"UPDATE {table} SET game_project_id = 'default_project' WHERE game_project_id IS NULL")
        
    # 3. Collision Checks (Preflight check)
    # Check duplicate slugs in npc_profiles
    res = bind.execute(sa.text(
        "SELECT game_project_id, slug, COUNT(*) FROM npc_profiles GROUP BY game_project_id, slug HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate slug records found in npc_profiles for composite unique constraint: {res}")
        
    # Check duplicate keys in world_state_flags
    res = bind.execute(sa.text(
        "SELECT game_project_id, flag_key, COUNT(*) FROM world_state_flags GROUP BY game_project_id, flag_key HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate flag_key records found in world_state_flags for composite unique constraint: {res}")

    # Check duplicate relationships in npc_relationships
    res = bind.execute(sa.text(
        "SELECT game_project_id, player_id, npc_slug, COUNT(*) FROM npc_relationships GROUP BY game_project_id, player_id, npc_slug HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate player/npc relationship records found in npc_relationships: {res}")
        
    # Check duplicate progress in quest_progress
    res = bind.execute(sa.text(
        "SELECT game_project_id, player_id, quest_id, COUNT(*) FROM quest_progress GROUP BY game_project_id, player_id, quest_id HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate player/quest progress records found in quest_progress: {res}")

    # Check duplicate slugs in world_entities
    res = bind.execute(sa.text(
        "SELECT game_project_id, slug, COUNT(*) FROM world_entities GROUP BY game_project_id, slug HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate slug records found in world_entities: {res}")

    # 4. Alter columns to non-nullable and set server default
    for table in tables_to_isolate:
        op.alter_column(table, 'game_project_id',
                        existing_type=sa.String(length=100),
                        nullable=False,
                        server_default='default_project')
                        
    # 5. Drop old constraints
    # Drop foreign keys first to avoid dependency issues when dropping unique/primary keys
    fk_drops = [
        ("quests", "quests_npc_slug_fkey"),
        ("quest_progress", "quest_progress_quest_id_fkey"),
        ("quest_progress", "quest_progress_quest_giver_slug_fkey"),
        ("generated_quests", "generated_quests_npc_slug_fkey"),
        ("npc_relationships", "npc_relationships_npc_slug_fkey"),
        ("conversations", "conversations_npc_id_fkey"),
        ("npc_memories", "npc_memories_npc_id_fkey"),
        ("npc_memories", "npc_memories_conversation_id_fkey")
    ]
    
    for table, fk in fk_drops:
        fks = [f['name'] for f in inspector.get_foreign_keys(table)]
        if fk in fks:
            op.drop_constraint(fk, table, type_='foreignkey')
            
    # Drop old unique/primary key constraints
    # npc_profiles_slug_key on npc_profiles
    uniques = [u['name'] for u in inspector.get_unique_constraints("npc_profiles")]
    if "npc_profiles_slug_key" in uniques:
        op.drop_constraint("npc_profiles_slug_key", "npc_profiles", type_='unique')
        
    # uq_entity_slug on world_entities
    uniques = [u['name'] for u in inspector.get_unique_constraints("world_entities")]
    if "uq_entity_slug" in uniques:
        op.drop_constraint("uq_entity_slug", "world_entities", type_='unique')

    # uq_player_npc on npc_relationships
    uniques = [u['name'] for u in inspector.get_unique_constraints("npc_relationships")]
    if "uq_player_npc" in uniques:
        op.drop_constraint("uq_player_npc", "npc_relationships", type_='unique')

    # uq_player_quest on quest_progress
    uniques = [u['name'] for u in inspector.get_unique_constraints("quest_progress")]
    if "uq_player_quest" in uniques:
        op.drop_constraint("uq_player_quest", "quest_progress", type_='unique')

    # world_state_flags_pkey on world_state_flags
    pk = inspector.get_pk_constraint("world_state_flags")
    if pk and pk.get("name") == "world_state_flags_pkey":
        op.drop_constraint("world_state_flags_pkey", "world_state_flags", type_='primary')

    # 6. Add new composite unique constraints / primary keys
    op.create_primary_key("world_state_flags_pkey", "world_state_flags", ["game_project_id", "flag_key"])
    op.create_unique_constraint("uq_npc_project_slug", "npc_profiles", ["game_project_id", "slug"])
    op.create_unique_constraint("uq_npc_project_id", "npc_profiles", ["game_project_id", "id"])
    op.create_unique_constraint("uq_quest_project_id", "quests", ["game_project_id", "id"])
    op.create_unique_constraint("uq_conversation_project_id", "conversations", ["game_project_id", "id"])
    op.create_unique_constraint("uq_entity_project_slug", "world_entities", ["game_project_id", "slug"])
    op.create_unique_constraint("uq_player_npc", "npc_relationships", ["game_project_id", "player_id", "npc_slug"])
    op.create_unique_constraint("uq_player_quest", "quest_progress", ["game_project_id", "player_id", "quest_id"])

    # 7. Re-create foreign keys as composite project-scoped references
    op.create_foreign_key(
        "quests_npc_slug_fkey",
        "quests",
        "npc_profiles",
        ["game_project_id", "npc_slug"],
        ["game_project_id", "slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "quest_progress_quest_giver_slug_fkey",
        "quest_progress",
        "npc_profiles",
        ["game_project_id", "quest_giver_slug"],
        ["game_project_id", "slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "quest_progress_quest_id_fkey",
        "quest_progress",
        "quests",
        ["game_project_id", "quest_id"],
        ["game_project_id", "id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "generated_quests_npc_slug_fkey",
        "generated_quests",
        "npc_profiles",
        ["game_project_id", "npc_slug"],
        ["game_project_id", "slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "npc_relationships_npc_slug_fkey",
        "npc_relationships",
        "npc_profiles",
        ["game_project_id", "npc_slug"],
        ["game_project_id", "slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "conversations_npc_id_fkey",
        "conversations",
        "npc_profiles",
        ["game_project_id", "npc_id"],
        ["game_project_id", "id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "npc_memories_npc_id_fkey",
        "npc_memories",
        "npc_profiles",
        ["game_project_id", "npc_id"],
        ["game_project_id", "id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "npc_memories_conversation_id_fkey",
        "npc_memories",
        "conversations",
        ["game_project_id", "conversation_id"],
        ["game_project_id", "id"],
        ondelete="SET NULL"
    )

    # 8. Create project-scoped indexes for all project-isolated tables scoped by this migration
    tables_to_index = [
        "npc_profiles",
        "world_state_flags",
        "npc_relationships",
        "quests",
        "quest_progress",
        "generated_quests",
        "conversations",
        "npc_memories",
        "world_entities"
    ]
    for table in tables_to_index:
        op.create_index(f'ix_{table}_game_project_id', table, ['game_project_id'], unique=False)



def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # 1. Collision Checks (Preflight check for downgrade)
    res = bind.execute(sa.text(
        "SELECT slug, COUNT(*) FROM npc_profiles GROUP BY slug HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate slug records found in npc_profiles; cannot downgrade project isolation: {res}")
        
    res = bind.execute(sa.text(
        "SELECT flag_key, COUNT(*) FROM world_state_flags GROUP BY flag_key HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate flag_key records found in world_state_flags; cannot downgrade project isolation: {res}")

    res = bind.execute(sa.text(
        "SELECT player_id, npc_slug, COUNT(*) FROM npc_relationships GROUP BY player_id, npc_slug HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate player/npc relationship records found in npc_relationships; cannot downgrade: {res}")
        
    res = bind.execute(sa.text(
        "SELECT player_id, quest_id, COUNT(*) FROM quest_progress GROUP BY player_id, quest_id HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate player/quest progress records found in quest_progress; cannot downgrade: {res}")

    res = bind.execute(sa.text(
        "SELECT slug, COUNT(*) FROM world_entities GROUP BY slug HAVING COUNT(*) > 1"
    )).fetchall()
    if res:
        raise RuntimeError(f"Duplicate slug records found in world_entities; cannot downgrade: {res}")

    # 2. Revert composite foreign keys
    fk_drops = [
        ("quests", "quests_npc_slug_fkey"),
        ("quest_progress", "quest_progress_quest_id_fkey"),
        ("quest_progress", "quest_progress_quest_giver_slug_fkey"),
        ("generated_quests", "generated_quests_npc_slug_fkey"),
        ("npc_relationships", "npc_relationships_npc_slug_fkey"),
        ("conversations", "conversations_npc_id_fkey"),
        ("npc_memories", "npc_memories_npc_id_fkey"),
        ("npc_memories", "npc_memories_conversation_id_fkey")
    ]
    for table, fk in fk_drops:
        fks = [f['name'] for f in inspector.get_foreign_keys(table)]
        if fk in fks:
            op.drop_constraint(fk, table, type_='foreignkey')

    # Drop composite unique/primary key constraints
    uniques = [u['name'] for u in inspector.get_unique_constraints("npc_profiles")]
    if "uq_npc_project_slug" in uniques:
        op.drop_constraint("uq_npc_project_slug", "npc_profiles", type_='unique')
    if "uq_npc_project_id" in uniques:
        op.drop_constraint("uq_npc_project_id", "npc_profiles", type_='unique')
        
    uniques = [u['name'] for u in inspector.get_unique_constraints("quests")]
    if "uq_quest_project_id" in uniques:
        op.drop_constraint("uq_quest_project_id", "quests", type_='unique')
        
    uniques = [u['name'] for u in inspector.get_unique_constraints("conversations")]
    if "uq_conversation_project_id" in uniques:
        op.drop_constraint("uq_conversation_project_id", "conversations", type_='unique')
        
    uniques = [u['name'] for u in inspector.get_unique_constraints("world_entities")]
    if "uq_entity_project_slug" in uniques:
        op.drop_constraint("uq_entity_project_slug", "world_entities", type_='unique')
        
    uniques = [u['name'] for u in inspector.get_unique_constraints("npc_relationships")]
    if "uq_player_npc" in uniques:
        op.drop_constraint("uq_player_npc", "npc_relationships", type_='unique')
        
    uniques = [u['name'] for u in inspector.get_unique_constraints("quest_progress")]
    if "uq_player_quest" in uniques:
        op.drop_constraint("uq_player_quest", "quest_progress", type_='unique')
        
    pk = inspector.get_pk_constraint("world_state_flags")
    if pk and pk.get("name") == "world_state_flags_pkey":
        op.drop_constraint("world_state_flags_pkey", "world_state_flags", type_='primary')

    # 3. Restore single-column unique/primary keys and foreign keys
    op.create_primary_key("world_state_flags_pkey", "world_state_flags", ["flag_key"])
    op.create_unique_constraint("npc_profiles_slug_key", "npc_profiles", ["slug"])
    op.create_unique_constraint("uq_entity_slug", "world_entities", ["slug"])
    op.create_unique_constraint("uq_player_npc", "npc_relationships", ["player_id", "npc_slug"])
    op.create_unique_constraint("uq_player_quest", "quest_progress", ["player_id", "quest_id"])

    op.create_foreign_key(
        "quests_npc_slug_fkey",
        "quests",
        "npc_profiles",
        ["npc_slug"],
        ["slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "quest_progress_quest_giver_slug_fkey",
        "quest_progress",
        "npc_profiles",
        ["quest_giver_slug"],
        ["slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "quest_progress_quest_id_fkey",
        "quest_progress",
        "quests",
        ["quest_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "generated_quests_npc_slug_fkey",
        "generated_quests",
        "npc_profiles",
        ["npc_slug"],
        ["slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "npc_relationships_npc_slug_fkey",
        "npc_relationships",
        "npc_profiles",
        ["npc_slug"],
        ["slug"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "conversations_npc_id_fkey",
        "conversations",
        "npc_profiles",
        ["npc_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "npc_memories_npc_id_fkey",
        "npc_memories",
        "npc_profiles",
        ["npc_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "npc_memories_conversation_id_fkey",
        "npc_memories",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL"
    )

    # 4. Drop project-scoped indexes
    tables_to_index = [
        "npc_profiles",
        "world_state_flags",
        "npc_relationships",
        "quests",
        "quest_progress",
        "generated_quests",
        "conversations",
        "npc_memories",
        "world_entities"
    ]
    for table in tables_to_index:
        op.drop_index(f'ix_{table}_game_project_id', table_name=table)

    # 5. Drop columns (game_project_id)
    tables_to_isolate = [
        "npc_profiles",
        "world_state_flags",
        "npc_relationships",
        "quests",
        "quest_progress",
        "generated_quests",
        "conversations",
        "npc_memories",
        "world_entities"
    ]
    for table in tables_to_isolate:
        columns = [c['name'] for c in inspector.get_columns(table)]
        if 'game_project_id' in columns:
            op.drop_column(table, 'game_project_id')
