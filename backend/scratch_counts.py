from app.database import SessionLocal, engine
from sqlalchemy import create_engine, text

def print_counts(db_engine, name):
    print(f"=== Database '{name}' Row Count Audit ===")
    tables = [
        "npc_profiles", "documents", "document_chunks", "conversations",
        "messages", "npc_memories", "llm_telemetry_logs", "world_state_flags",
        "npc_relationships", "quests", "quest_objectives", "quest_progress"
    ]
    for t in tables:
        with db_engine.connect() as conn:
            try:
                cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                print(f"  Table '{t}': {cnt} rows")
            except Exception as e:
                # print class name of exception
                print(f"  Table '{t}': ERROR ({type(e).__name__})")

print_counts(engine, "gamemind")
test_engine = create_engine("postgresql://postgres:postgres@db:5432/gamemind_test")
print_counts(test_engine, "gamemind_test")

