import os
import sys
from pathlib import Path

# Load the local test file when present. CI supplies the same settings through
# explicit environment variables because secret-style .env files are not
# committed to the repository.
backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent

env_test_path = backend_dir / ".env.test"
if not env_test_path.exists():
    env_test_path = project_root / ".env.test"

if env_test_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_test_path, override=True)
    os.environ["GAMEMIND_TESTING"] = "1"
elif os.getenv("GAMEMIND_TESTING") != "1":
    raise RuntimeError(
        "Tests require either backend/.env.test or explicit CI test "
        "environment variables with GAMEMIND_TESTING=1."
    )

database_url = os.getenv("DATABASE_URL", "")
if "gamemind_test" not in database_url:
    raise RuntimeError(
        "Refusing to initialize tests because DATABASE_URL does not target "
        f"gamemind_test: {database_url or '<unset>'}"
    )

# Now add backend_dir to sys.path if not present
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.config import settings
from main import app

# Verify that Pydantic resolved the same safe database after application import.
assert "gamemind_test" in settings.DATABASE_URL, (
    f"Database URL does not point to test database: {settings.DATABASE_URL}"
)

# Create the test engine
test_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Session-scoped fixture to drop and recreate all tables once for the test run."""
    # Ensure tables are created in the test database
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    # Cleanup at the very end
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(autouse=True)
def db_session():
    """
    Function-scoped fixture to yield database session and clean up dependencies.
    """
    session = TestSessionLocal()
    
    # Overwrite the FastAPI get_db dependency to yield this session
    def override_get_db():
        try:
            yield session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    session.close()
    app.dependency_overrides.pop(get_db, None)
