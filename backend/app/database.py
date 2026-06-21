from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from sqlalchemy import Column, String

class ProjectScopedMixin:
    game_project_id = Column(
        String(100),
        nullable=False,
        index=True,
        server_default="default_project",
        default="default_project"
    )

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

