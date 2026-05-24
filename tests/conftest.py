import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.database import Base, get_db
from app.models import SplatCapture, ProcessingJob
from app.main import app

# Use a temporary file-based SQLite database with NullPool to prevent connection lockups
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_temp.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh clean database schema for each single test function.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up tables
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_db():
    """
    Ensures that the temporary SQLite test database file is removed after the entire test suite runs.
    """
    yield
    if os.path.exists("test_temp.db"):
        try:
            os.remove("test_temp.db")
        except OSError:
            pass


@pytest.fixture(scope="function")
def client(db_session):
    """
    Overrides the FastAPI get_db dependency with the isolated test session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
