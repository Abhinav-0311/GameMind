import os
import sys
from pathlib import Path

# 1. Force loading of .env.test BEFORE importing any app modules
backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent
env_test_path = project_root / ".env.test"

if env_test_path.exists():
    from dotenv import load_dotenv
    # override=True ensures we override the default system or pre-loaded env variables
    load_dotenv(dotenv_path=env_test_path, override=True)
    # Also set an explicit environment flag so we can assert we are in test mode
    os.environ["GAMEMIND_TESTING"] = "1"
else:
    raise RuntimeError(f"Required test configuration file .env.test not found at {env_test_path}")

# Now add backend_dir to sys.path if not present
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.config import settings
from main import app

# Verify that settings indeed resolved to the test database
assert "gamemind_test" in settings.DATABASE_URL, f"Database URL does not point to test database: {settings.DATABASE_URL}"

# Create the test engine
test_engine = create_engine(settings.DATABASE_URL)
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
