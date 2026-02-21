import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

# ── Test database — uses SQLite in-memory so tests don't need a real Postgres ─
SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

test_engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once before tests, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Fresh DB session per test — rolls back after each test."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db):
    """FastAPI test client with DB override injected."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# TODO: Add test fixtures for a pre-created user, hotel, room as needed
# Example:
#   @pytest.fixture
#   def test_user(db):
#       from app.services.auth_service import sign_up
#       from app.schemas.auth import SignUpRequest
#       return sign_up(db, SignUpRequest(name="Test", email="test@test.com", password="password123"))
