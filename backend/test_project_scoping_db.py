import pytest
import uuid
import os
import sys
import subprocess
import time
import httpx
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal, Base
from app.models.npc import NPCProfile
from app.models.world_state import WorldStateFlag
from app.models.graph import WorldEntity, WorldRelationship
from app.models.quest import Quest, QuestProgress
from app.models.relationship import NPCRelationship
from app.models.document import Document

client = TestClient(app)

@pytest.fixture(scope="function")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()

@pytest.fixture(scope="function")
def db_migration_lock():
    """Acquires a database-level advisory lock to serialize migration integration tests."""
    from app.config import settings
    base_url, _ = settings.DATABASE_URL.rsplit("/", 1)
    admin_url = f"{base_url}/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    
    conn = admin_engine.connect()
    conn.execute(text("SELECT pg_advisory_lock(987654)"))
    try:
        yield
    finally:
        conn.execute(text("SELECT pg_advisory_unlock(987654)"))
        conn.close()

def run_alembic(temp_db_url, args):
    """Executes Alembic command in a subprocess with environment isolation."""
    env = os.environ.copy()
    env["DATABASE_URL"] = temp_db_url
    res = subprocess.run(
        [sys.executable, "-m", "alembic"] + args,
        cwd="/app" if os.path.exists("/app/alembic.ini") else "backend" if os.path.exists("backend/alembic.ini") else ".",
        env=env,
        capture_output=True,
        text=True
    )
    return res

def test_two_projects_same_npc_slug(db: Session):
    """Verify two projects can create the same NPC slug."""
    project_a = f"proj_a_{uuid.uuid4().hex[:6]}"
    project_b = f"proj_b_{uuid.uuid4().hex[:6]}"
    slug = f"npc_{uuid.uuid4().hex[:6]}"

    npc_a = NPCProfile(
        slug=slug,
        name="Sir Galahad",
        personality_summary="Knight A",
        game_project_id=project_a
    )
    npc_b = NPCProfile(
        slug=slug,
        name="Sir Lancelot",
        personality_summary="Knight B",
        game_project_id=project_b
    )
    db.add(npc_a)
    db.add(npc_b)
    db.commit()

    # Verify both exist as separate rows
    count = db.query(NPCProfile).filter(NPCProfile.slug == slug).count()
    assert count == 2

def test_two_projects_same_world_flag_key(db: Session):
    """Verify two projects can create the same world flag key."""
    project_a = f"proj_a_{uuid.uuid4().hex[:6]}"
    project_b = f"proj_b_{uuid.uuid4().hex[:6]}"
    key = f"flag_{uuid.uuid4().hex[:6]}"

    flag_a = WorldStateFlag(
        flag_key=key,
        flag_value="true",
        game_project_id=project_a
    )
    flag_b = WorldStateFlag(
        flag_key=key,
        flag_value="false",
        game_project_id=project_b
    )
    db.add(flag_a)
    db.add(flag_b)
    db.commit()

    count = db.query(WorldStateFlag).filter(WorldStateFlag.flag_key == key).count()
    assert count == 2

def test_two_projects_same_world_entity_slug(db: Session):
    """Verify two projects can create the same world entity slug."""
    project_a = f"proj_a_{uuid.uuid4().hex[:6]}"
    project_b = f"proj_b_{uuid.uuid4().hex[:6]}"
    slug = f"ent_{uuid.uuid4().hex[:6]}"

    ent_a = WorldEntity(
        slug=slug,
        entity_type="item",
        game_project_id=project_a
    )
    ent_b = WorldEntity(
        slug=slug,
        entity_type="item",
        game_project_id=project_b
    )
    db.add(ent_a)
    db.add(ent_b)
    db.commit()

    count = db.query(WorldEntity).filter(WorldEntity.slug == slug).count()
    assert count == 2

def test_quest_cannot_reference_npc_from_other_project(db: Session):
    """Verify a quest cannot reference an NPC from another project."""
    project_a = f"proj_a_{uuid.uuid4().hex[:6]}"
    project_b = f"proj_b_{uuid.uuid4().hex[:6]}"
    npc_slug = f"npc_{uuid.uuid4().hex[:6]}"

    # Create NPC in Project A
    npc = NPCProfile(
        slug=npc_slug,
        name="Quest Giver A",
        personality_summary="Summary",
        game_project_id=project_a
    )
    db.add(npc)
    db.commit()

    # Attempt to create Quest in Project B referencing NPC in Project A
    quest = Quest(
        id=uuid.uuid4(),
        npc_slug=npc_slug,
        title="Cross-Project Quest",
        description="This should fail due to FK constraints",
        game_project_id=project_b  # Mismatch
    )
    db.add(quest)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_quest_progress_cannot_reference_quest_from_other_project(db: Session):
    """Verify quest progress cannot reference a quest from another project."""
    project_a = f"proj_a_{uuid.uuid4().hex[:6]}"
    project_b = f"proj_b_{uuid.uuid4().hex[:6]}"
    npc_slug = f"npc_{uuid.uuid4().hex[:6]}"

    # Create NPC and Quest in Project A
    npc = NPCProfile(
        slug=npc_slug,
        name="Quest Giver A",
        personality_summary="Summary",
        game_project_id=project_a
    )
    db.add(npc)
    db.commit()

    quest = Quest(
        id=uuid.uuid4(),
        npc_slug=npc_slug,
        title="Quest A",
        description="Quest in A",
        game_project_id=project_a
    )
    db.add(quest)
    db.commit()

    # Attempt to create QuestProgress in Project B referencing Quest in Project A
    progress = QuestProgress(
        quest_id=quest.id,
        player_id="test_player",
        quest_giver_slug=npc_slug,
        status="active",
        game_project_id=project_b  # Mismatch
    )
    db.add(progress)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_relationship_cannot_reference_npc_from_other_project(db: Session):
    """Verify relationships cannot reference an NPC from another project."""
    project_a = f"proj_a_{uuid.uuid4().hex[:6]}"
    project_b = f"proj_b_{uuid.uuid4().hex[:6]}"
    npc_slug = f"npc_{uuid.uuid4().hex[:6]}"

    # Create NPC in Project A
    npc = NPCProfile(
        slug=npc_slug,
        name="Knight A",
        personality_summary="Summary",
        game_project_id=project_a
    )
    db.add(npc)
    db.commit()

    # Attempt to create Relationship in Project B referencing NPC in Project A
    rel = NPCRelationship(
        player_id="test_player",
        npc_slug=npc_slug,
        trust=60,
        respect=60,
        friendship=60,
        fear=10,
        game_project_id=project_b  # Mismatch
    )
    db.add(rel)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_cross_project_api_reads_return_404(db: Session):
    """Verify cross-project API reads return 404."""
    project_a = f"proj_a_{uuid.uuid4().hex[:6]}"
    project_b = f"proj_b_{uuid.uuid4().hex[:6]}"
    npc_slug = f"npc_{uuid.uuid4().hex[:6]}"

    # Create NPC in Project A
    npc = NPCProfile(
        slug=npc_slug,
        name="Galahad",
        personality_summary="Galahad",
        game_project_id=project_a
    )
    db.add(npc)
    db.commit()
    npc_id = npc.id

    # Query NPC via API using Project B project ID
    headers_b = {"X-Game-Project-ID": project_b}
    res = client.get(f"/api/v1/npcs/{npc_id}", headers=headers_b)
    assert res.status_code == 404


@pytest.mark.integration
@pytest.mark.serial
def test_clean_db_migration(db_migration_lock):
    """Verify that migrations can build a clean database from scratch with exact schema properties."""
    from app.config import settings
    base_url, _ = settings.DATABASE_URL.rsplit("/", 1)
    admin_url = f"{base_url}/postgres"
    temp_db_name = f"temp_clean_test_{uuid.uuid4().hex[:8]}"
    temp_db_url = f"{base_url}/{temp_db_name}"

    # Create temp DB
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {temp_db_name}"))

    try:
        # Run Alembic upgrade head in subprocess
        res = run_alembic(temp_db_url, ["upgrade", "head"])
        assert res.returncode == 0, f"Alembic upgrade head failed: {res.stderr}"

        # Connect and inspect schema
        temp_engine = create_engine(temp_db_url)
        inspector = sa.inspect(temp_engine)
        tables = inspector.get_table_names()

        # 1. Assert all tables exist and match metadata exactly
        expected_tables = set(Base.metadata.tables.keys()) | {"alembic_version"}
        assert set(tables) == expected_tables, f"Table set mismatch. Reflected: {tables}, Expected: {expected_tables}"

        # 2. Assert current revision equals head
        heads_res = run_alembic(temp_db_url, ["heads"])
        assert heads_res.returncode == 0
        with temp_engine.connect() as conn:
            current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert current_rev is not None
        assert current_rev in heads_res.stdout

        # 3. Assert indexes & constraints exist
        # Check composite foreign keys on world_relationships
        fks = inspector.get_foreign_keys('world_relationships')
        src_fk = next(fk for fk in fks if fk['name'] == 'fk_world_relationships_source')
        assert src_fk['referred_table'] == 'world_entities'
        assert src_fk['referred_columns'] == ['game_project_id', 'id']
        assert src_fk['constrained_columns'] == ['game_project_id', 'source_id']
        assert src_fk['options'].get('ondelete') == 'CASCADE'

        # Check server defaults
        cols = inspector.get_columns('documents')
        proj_col = next(c for c in cols if c['name'] == 'game_project_id')
        assert proj_col['default'] is not None
        assert 'default_project' in proj_col['default']

        # 4. Verify application can create session and query
        SessionTemp = sessionmaker(bind=temp_engine)
        session = SessionTemp()
        try:
            session.query(NPCProfile).all()
        finally:
            session.close()

        # 5. Launch FastAPI health check in subprocess with DATABASE_URL
        env = os.environ.copy()
        env["DATABASE_URL"] = temp_db_url
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8099"],
            cwd="/app" if os.path.exists("/app/main.py") else ".",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            started = False
            for _ in range(30):
                time.sleep(0.5)
                try:
                    h_res = httpx.get("http://127.0.0.1:8099/health")
                    if h_res.status_code == 200:
                        started = True
                        break
                except Exception:
                    pass
            assert started, "FastAPI server failed to start successfully bound to temporary database URL."
        finally:
            proc.terminate()
            proc.wait()

    finally:
        # Cleanup temp DB
        try:
            with admin_engine.connect() as conn:
                conn.execute(text(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{temp_db_name}'
                      AND pid <> pg_backend_pid();
                """))
                conn.execute(text(f"DROP DATABASE IF EXISTS {temp_db_name}"))
        except Exception as e:
            print(f"Failed to drop database: {e}")


@pytest.mark.integration
@pytest.mark.serial
def test_schema_parity_with_metadata(db_migration_lock):
    """Verify reflected database tables match SQLAlchemy metadata properties exactly."""
    from app.config import settings
    base_url, _ = settings.DATABASE_URL.rsplit("/", 1)
    admin_url = f"{base_url}/postgres"
    temp_db_name = f"temp_parity_test_{uuid.uuid4().hex[:8]}"
    temp_db_url = f"{base_url}/{temp_db_name}"

    # Create temp DB
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {temp_db_name}"))

    def normalize_default_val(val_str):
        if not val_str:
            return ""
        val_str = str(val_str).strip()
        # Strip outer parentheses
        while val_str.startswith("(") and val_str.endswith(")"):
            val_str = val_str[1:-1].strip()
        # Normalize spaces and casing
        val_str = " ".join(val_str.split()).lower()
        # Strip quotes
        val_str = val_str.replace("'", "").replace('"', "")
        # Remove standard Postgres type casts at the end of string or expressions
        import re
        val_str = re.sub(r'::[a-z0-9_ ]+(?:\([0-9, ]+\))?', '', val_str)
        # Normalize interval notations
        val_str = val_str.replace("interval 1 hour", "1 hour")
        val_str = val_str.replace("01:00:00::interval", "1 hour")
        val_str = val_str.replace("01:00:00", "1 hour")
        # Strip any remaining typecasts if they missed
        val_str = val_str.replace("::jsonb", "").replace("::text", "")
        return val_str.strip()

    mismatches = []
    try:
        # Run Alembic upgrade head in subprocess
        res = run_alembic(temp_db_url, ["upgrade", "head"])
        assert res.returncode == 0, f"Alembic upgrade head failed: {res.stderr}"

        # Connect and inspect schema
        temp_engine = create_engine(temp_db_url)
        inspector = sa.inspect(temp_engine)
        reflected_metadata = sa.MetaData()
        reflected_metadata.reflect(bind=temp_engine)

        reflected_tables = inspector.get_table_names()
        expected_tables = set(Base.metadata.tables.keys()) | {"alembic_version"}
        if set(reflected_tables) != expected_tables:
            mismatches.append(f"Table set mismatch: reflected={reflected_tables}, expected={expected_tables}")

        for table_name, table in Base.metadata.tables.items():
            if table_name not in reflected_metadata.tables:
                mismatches.append(f"Table {table_name} missing from active database")
                continue

            columns = inspector.get_columns(table_name)
            pks = inspector.get_pk_constraint(table_name)
            fks = inspector.get_foreign_keys(table_name)
            uniques = inspector.get_unique_constraints(table_name)
            indexes = inspector.get_indexes(table_name)

            reflected_cols_dict = {c['name']: c for c in columns}

            # 1. Compare Columns
            for col in table.columns:
                if col.name not in reflected_cols_dict:
                    mismatches.append(f"Column {table_name}.{col.name} missing from database")
                    continue
                reflected_col = reflected_cols_dict[col.name]

                # Type normalization & comparison
                t1 = str(col.type).lower().split("(")[0]
                t2 = str(reflected_col['type']).lower().split("(")[0]
                type_mapping = {
                    "varchar": "string",
                    "character varying": "string",
                    "double precision": "float",
                    "datetime": "timestamp",
                    "timestamp with time zone": "timestamp",
                    "timestamp without time zone": "timestamp",
                    "jsonb": "json"
                }
                t1_norm = type_mapping.get(t1, t1)
                t2_norm = type_mapping.get(t2, t2)
                if t1_norm != t2_norm and not (t1_norm in ["string", "text"] and t2_norm in ["string", "text"]):
                    mismatches.append(f"Type mismatch for {table_name}.{col.name}: metadata={t1} ({t1_norm}), database={t2} ({t2_norm})")

                # Nullability comparison
                if col.nullable != reflected_col['nullable']:
                    mismatches.append(f"Nullability mismatch for {table_name}.{col.name}: metadata={col.nullable}, database={reflected_col['nullable']}")

                # Server default vs Python client-side default comparison
                actual_default = reflected_col['default']
                if col.server_default is not None:
                    if actual_default is None:
                        mismatches.append(f"Expected server default for {table_name}.{col.name} but got None")
                    else:
                        # Extract the default value
                        if hasattr(col.server_default.arg, 'text'):
                            expected_raw = col.server_default.arg.text
                        else:
                            expected_raw = str(col.server_default.arg)

                        norm_expected = normalize_default_val(expected_raw)
                        norm_actual = normalize_default_val(actual_default)

                        if norm_expected != norm_actual and norm_expected not in norm_actual and norm_actual not in norm_expected:
                            mismatches.append(f"Server default mismatch for {table_name}.{col.name}: metadata={expected_raw} (norm={norm_expected}), database={actual_default} (norm={norm_actual})")
                else:
                    # If server default is None, ensure database default is None (excluding non-serial primary keys or autoincrement keys)
                    if not col.primary_key and actual_default is not None:
                        mismatches.append(f"Unexpected server default for {table_name}.{col.name}: database default={actual_default}")

            # 2. Compare Primary Keys
            expected_pk_cols = [c.name for c in table.primary_key.columns]
            actual_pk_cols = pks.get('constrained_columns', [])
            if set(expected_pk_cols) != set(actual_pk_cols):
                mismatches.append(f"Primary key mismatch for table {table_name}: expected {expected_pk_cols}, got {actual_pk_cols}")

            # 3. Compare Foreign Keys
            for fk_constraint in table.foreign_key_constraints:
                expected_fk = {
                    'constrained_columns': [c.name for c in fk_constraint.columns],
                    'referred_table': fk_constraint.referred_table.name,
                    'referred_columns': [elem.column.name for elem in fk_constraint.elements],
                    'ondelete': str(fk_constraint.ondelete).upper() if fk_constraint.ondelete else None
                }

                # Match by constrained columns and referred table
                match = None
                for afk in fks:
                    if (afk['referred_table'] == expected_fk['referred_table'] and
                        set(afk['constrained_columns']) == set(expected_fk['constrained_columns'])):
                        match = afk
                        break

                if match is None:
                    mismatches.append(f"Foreign key missing in database for table {table_name}: expected referred_table={expected_fk['referred_table']}, columns={expected_fk['constrained_columns']}")
                else:
                    # Verify referred columns
                    if set(match['referred_columns']) != set(expected_fk['referred_columns']):
                        mismatches.append(f"Foreign key referred columns mismatch for table {table_name}: expected {expected_fk['referred_columns']}, got {match['referred_columns']}")
                    # Verify ondelete cascade action
                    actual_ondelete = match.get('options', {}).get('ondelete')
                    actual_ondelete = str(actual_ondelete).upper() if actual_ondelete else None
                    if actual_ondelete != expected_fk['ondelete']:
                        mismatches.append(f"Foreign key ondelete action mismatch for table {table_name}: expected {expected_fk['ondelete']}, got {actual_ondelete}")

            # 4. Compare Unique Constraints
            for constraint in table.constraints:
                if isinstance(constraint, sa.UniqueConstraint):
                    expected_cols = [c.name for c in constraint.columns]

                    # Match by column set
                    match = None
                    for auq in uniques:
                        if set(auq['column_names']) == set(expected_cols):
                            match = auq
                            break
                    if match is None:
                        # Check if implemented as a unique index
                        for idx in indexes:
                            if idx['unique'] and set(idx['column_names']) == set(expected_cols):
                                match = idx
                                break
                    if match is None:
                        mismatches.append(f"Unique constraint/index missing in database for table {table_name}: expected columns {expected_cols}")

            # 5. Compare Indexes
            for index in table.indexes:
                expected_idx = {
                    'name': index.name,
                    'column_names': [c.name for c in index.columns],
                    'unique': index.unique
                }

                match = next((idx for idx in indexes if idx['name'] == expected_idx['name']), None)
                if match is None:
                    match = next((idx for idx in indexes if set(idx['column_names']) == set(expected_idx['column_names'])), None)

                if match is None:
                    mismatches.append(f"Index missing in database for table {table_name}: name={expected_idx['name']}, columns={expected_idx['column_names']}")
                else:
                    if match['unique'] != expected_idx['unique']:
                        mismatches.append(f"Index uniqueness mismatch for table {table_name} index {expected_idx['name']}: expected {expected_idx['unique']}, got {match['unique']}")

        assert not mismatches, "Schema parity mismatches found:\n" + "\n".join(mismatches)

    finally:
        # Cleanup temp DB
        try:
            with admin_engine.connect() as conn:
                conn.execute(text(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{temp_db_name}'
                      AND pid <> pg_backend_pid();
                """))
                conn.execute(text(f"DROP DATABASE IF EXISTS {temp_db_name}"))
        except Exception as e:
            print(f"Failed to drop database: {e}")


@pytest.mark.integration
@pytest.mark.serial
def test_migration_downgrade_collision(db_migration_lock):
    """Verify that downgrade to pre-scoping fails when duplicate slugs across projects exist."""
    from app.config import settings
    base_url, _ = settings.DATABASE_URL.rsplit("/", 1)
    admin_url = f"{base_url}/postgres"
    temp_db_name = f"temp_clean_test_{uuid.uuid4().hex[:8]}"
    temp_db_url = f"{base_url}/{temp_db_name}"

    # Create temp DB
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {temp_db_name}"))

    try:
        # 1. Run migrations up to head
        res = run_alembic(temp_db_url, ["upgrade", "head"])
        assert res.returncode == 0

        # 2. Seed duplicate NPC slugs under different projects
        temp_engine = create_engine(temp_db_url)
        with temp_engine.connect() as conn:
            # Seed projects
            conn.execute(text(f"""
                INSERT INTO npc_profiles (id, slug, name, personality_summary, game_project_id)
                VALUES 
                    ('{uuid.uuid4()}', 'knight', 'Galahad', 'Knight A', 'proj_a'),
                    ('{uuid.uuid4()}', 'knight', 'Lancelot', 'Knight B', 'proj_b');
            """))
            conn.commit()

        # 3. Attempt downgrade to cb61e6326352 (pre-isolation version) in subprocess
        res = run_alembic(temp_db_url, ["downgrade", "cb61e6326352"])
        assert res.returncode != 0, "Downgrade should have failed due to duplicate slugs constraint collision"
        assert "RuntimeError" in res.stderr or "Duplicate slug" in res.stderr

        # 4. Verify DB remains at head and constraints/rows are intact
        with temp_engine.connect() as conn:
            current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            # Assert head revision remains
            heads_res = run_alembic(temp_db_url, ["heads"])
            assert current_rev in heads_res.stdout

            # Verify both rows are still there
            rows = conn.execute(text("SELECT slug, game_project_id FROM npc_profiles WHERE slug='knight'")).fetchall()
            assert len(rows) == 2

            # Verify composite constraint is still there (reflected unique constraints)
            inspector = sa.inspect(temp_engine)
            uniques = [u['name'] for u in inspector.get_unique_constraints('npc_profiles')]
            assert 'uq_npc_project_slug' in uniques

    finally:
        # Cleanup temp DB
        try:
            with admin_engine.connect() as conn:
                conn.execute(text(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{temp_db_name}'
                      AND pid <> pg_backend_pid();
                """))
                conn.execute(text(f"DROP DATABASE IF EXISTS {temp_db_name}"))
        except Exception as e:
            print(f"Failed to drop database: {e}")
