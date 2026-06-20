from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _get_connection(engine_or_conn):
    if hasattr(engine_or_conn, "connect"):
        return engine_or_conn.connect()
    
    # It's already a connection-like object, wrap it in a dummy context manager
    class DummyContext:
        def __init__(self, conn):
            self.conn = conn
        def __enter__(self):
            return self.conn
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    return DummyContext(engine_or_conn)

def _execute_and_commit(conn, statement):
    from sqlalchemy import text
    if isinstance(statement, str):
        stmt = text(statement)
    else:
        stmt = statement
        
    res = conn.execute(stmt)
    if hasattr(conn, "in_transaction") and conn.in_transaction():
        pass
    else:
        try:
            conn.commit()
        except Exception:
            pass
    return res

def ensure_phase_9c_schema(engine):
    """Dynamically applies schema updates for Phase 9C if columns do not exist."""
    add_cols = [
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_summarized_message_id UUID;",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS summary_version INTEGER NOT NULL DEFAULT 0;",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE npc_memories ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;"
    ]
    with _get_connection(engine) as conn:
        try:
            _execute_and_commit(conn, "ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_last_summarized_message_id_fkey;")
        except Exception:
            pass

        for q in add_cols:
            try:
                _execute_and_commit(conn, q)
            except Exception:
                pass
                
        # Add exact constraint matching SQLAlchemy model name if not present
        try:
            check_constraint = "SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'fk_conversations_last_summarized_message' AND table_name = 'conversations';"
            exists = conn.execute(text(check_constraint)).first()
            if not exists:
                add_constraint = "ALTER TABLE conversations ADD CONSTRAINT fk_conversations_last_summarized_message FOREIGN KEY (last_summarized_message_id) REFERENCES messages(id) ON DELETE SET NULL;"
                _execute_and_commit(conn, add_constraint)
        except Exception:
            pass

def ensure_phase_9d_schema(engine):
    """Idempotently adds the llm_telemetry_logs table and its indexes if not exists."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS llm_telemetry_logs (
        id UUID PRIMARY KEY,
        conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
        action_type VARCHAR(50) NOT NULL,
        npc_slug VARCHAR(100) NOT NULL,
        model_used VARCHAR(100) NOT NULL,
        llm_provider VARCHAR(50) NOT NULL,
        latency_ms INTEGER NOT NULL,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0.000000,
        safety_blocked BOOLEAN NOT NULL DEFAULT FALSE,
        safety_ratings JSONB,
        error VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """
    with _get_connection(engine) as conn:
        try:
            _execute_and_commit(conn, create_table_query)
        except Exception:
            pass

        # Create indexes idempotently
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_llm_telemetry_logs_created_at ON llm_telemetry_logs (created_at);",
            "CREATE INDEX IF NOT EXISTS ix_llm_telemetry_logs_npc_slug ON llm_telemetry_logs (npc_slug);",
            "CREATE INDEX IF NOT EXISTS ix_llm_telemetry_logs_action_type ON llm_telemetry_logs (action_type);",
            "CREATE INDEX IF NOT EXISTS ix_llm_telemetry_logs_conversation_id ON llm_telemetry_logs (conversation_id);"
        ]
        for q in indexes:
            try:
                _execute_and_commit(conn, q)
            except Exception:
                pass

def ensure_phase_3a_schema(engine):
    """Idempotently creates the world_state_flags and npc_relationships tables if not exists."""
    create_world_state_query = """
    CREATE TABLE IF NOT EXISTS world_state_flags (
        flag_key VARCHAR(100) PRIMARY KEY,
        flag_value TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        priority INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """
    create_relationships_query = """
    CREATE TABLE IF NOT EXISTS npc_relationships (
        id UUID PRIMARY KEY,
        player_id VARCHAR(100) NOT NULL DEFAULT 'default_player',
        npc_slug VARCHAR(100) NOT NULL REFERENCES npc_profiles(slug) ON DELETE CASCADE,
        trust INTEGER NOT NULL DEFAULT 50 CHECK (trust BETWEEN 0 AND 100),
        respect INTEGER NOT NULL DEFAULT 50 CHECK (respect BETWEEN 0 AND 100),
        friendship INTEGER NOT NULL DEFAULT 50 CHECK (friendship BETWEEN 0 AND 100),
        fear INTEGER NOT NULL DEFAULT 0 CHECK (fear BETWEEN 0 AND 100),
        last_reason TEXT NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_player_npc UNIQUE (player_id, npc_slug)
    );
    """
    with _get_connection(engine) as conn:
        try:
            _execute_and_commit(conn, create_world_state_query)
        except Exception:
            pass

        try:
            _execute_and_commit(conn, create_relationships_query)
        except Exception:
            pass

def ensure_phase_3b_schema(engine):
    """Idempotently adds quests, objectives, and player-scoped quest progress tables, and alters memories."""
    alter_memory_query = "ALTER TABLE npc_memories ADD COLUMN IF NOT EXISTS metadata JSONB NULL;"
    create_quests_query = """
    CREATE TABLE IF NOT EXISTS quests (
        id UUID PRIMARY KEY,
        npc_slug VARCHAR(100) NOT NULL REFERENCES npc_profiles(slug) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        difficulty VARCHAR(50) NOT NULL DEFAULT 'Medium',
        gold_reward INTEGER NOT NULL DEFAULT 0,
        xp_reward INTEGER NOT NULL DEFAULT 0,
        item_rewards JSONB NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """
    create_objectives_query = """
    CREATE TABLE IF NOT EXISTS quest_objectives (
        id UUID PRIMARY KEY,
        quest_id UUID NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
        objective_index INTEGER NOT NULL,
        description TEXT NOT NULL,
        target_type VARCHAR(50) NOT NULL,
        target_id VARCHAR(100) NOT NULL,
        quantity_required INTEGER NOT NULL DEFAULT 1,
        CONSTRAINT uq_quest_objective_index UNIQUE (quest_id, objective_index)
    );
    """
    create_progress_query = """
    CREATE TABLE IF NOT EXISTS quest_progress (
        id UUID PRIMARY KEY,
        player_id VARCHAR(100) NOT NULL DEFAULT 'default_player',
        quest_id UUID NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
        quest_giver_slug VARCHAR(100) NOT NULL REFERENCES npc_profiles(slug) ON DELETE CASCADE,
        status VARCHAR(50) NOT NULL DEFAULT 'active',
        objectives_state JSONB NOT NULL,
        started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMP WITH TIME ZONE NULL,
        failed_at TIMESTAMP WITH TIME ZONE NULL,
        CONSTRAINT uq_player_quest UNIQUE (player_id, quest_id)
    );
    """
    with _get_connection(engine) as conn:
        for q in [alter_memory_query, create_quests_query, create_objectives_query, create_progress_query]:
            try:
                _execute_and_commit(conn, q)
            except Exception:
                pass

def ensure_schema_with_advisory_lock(engine):
    """
    Acquires a transaction-level PostgreSQL advisory lock (7426391) to serialize 
    startup database schema updates, preventing concurrent race conditions.
    Records lock acquisition time and logs it to telemetry.
    """
    import time
    from sqlalchemy import text
    from app.services.telemetry_service import TelemetryService
    
    start_time = time.time()
    with engine.begin() as conn:
        # pg_advisory_xact_lock is automatically released when transaction ends
        conn.execute(text("SELECT pg_advisory_xact_lock(7426391);"))
        end_time = time.time()
        lock_wait_ms = int((end_time - start_time) * 1000)
        
        # Execute DDL statements under lock
        ensure_phase_9c_schema(conn)
        ensure_phase_9d_schema(conn)
        ensure_phase_3a_schema(conn)
        ensure_phase_3b_schema(conn)
        
        # Create metadata defined tables if they do not exist
        Base.metadata.create_all(bind=conn)
        
    # Persist lock wait latency metric using a separate SessionLocal connection
    db = SessionLocal()
    try:
        TelemetryService.record_graph_schema_lock_wait(db, lock_wait_ms)
    except Exception as e:
        print(f"Failed to record schema lock wait telemetry: {e}")
    finally:
        db.close()



