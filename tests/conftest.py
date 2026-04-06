import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, BigInteger
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

# ── SQLite compatibility: map BigInteger → INTEGER so autoincrement works ──────
# SQLite only auto-increments "INTEGER PRIMARY KEY", not "BIGINT PRIMARY KEY".
# @compiles intercepts DDL at CREATE TABLE time for the SQLite dialect only.
@compiles(BigInteger, "sqlite")
def bi_sqlite(element, compiler, **kw):
    return "INTEGER"

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


# ── Auth header fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def guest_headers(client, db):
    """Auth headers for a GUEST user."""
    client.post("/auth/signup", json={
        "name": "Test Guest",
        "email": "guest@test.com",
        "password": "password123"
    })
    resp = client.post("/auth/login", json={
        "email": "guest@test.com",
        "password": "password123"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manager_headers(client, db):
    """Auth headers for a HOTEL_MANAGER user — role set directly in DB."""
    from app.models.user import User, UserRole
    from app.models.enums import RoleEnum

    client.post("/auth/signup", json={
        "name": "Test Manager",
        "email": "manager@test.com",
        "password": "password123"
    })
    # Assign HOTEL_MANAGER role directly in DB (idempotent — skip if already set)
    user = db.query(User).filter(User.email == "manager@test.com").first()
    existing_role = db.query(UserRole).filter(
        UserRole.user_id == user.id,
        UserRole.role == RoleEnum.HOTEL_MANAGER.value
    ).first()
    if not existing_role:
        db.add(UserRole(user_id=user.id, role=RoleEnum.HOTEL_MANAGER.value))
        db.commit()

    resp = client.post("/auth/login", json={
        "email": "manager@test.com",
        "password": "password123"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Hotel / Room fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def test_hotel(client, manager_headers):
    """Create a hotel via API and return its response JSON."""
    resp = client.post("/admin/hotels", headers=manager_headers, json={
        "name": "Test Hotel",
        "city": "Austin",
        "photos": [],
        "amenities": [],
        "contact_phone": "5551234567",
        "contact_email": "hotel@test.com",
        "contact_address": "123 Main St",
        "contact_location": "30.2672,-97.7431"
    })
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def active_hotel(client, manager_headers, test_hotel):
    """Activate the hotel and add a room (triggers 365 inventory rows)."""
    hotel_id = test_hotel["id"]
    client.patch(f"/admin/hotels/{hotel_id}/activate", headers=manager_headers)

    room_resp = client.post(f"/admin/hotels/{hotel_id}/rooms", headers=manager_headers, json={
        "type": "STANDARD",
        "base_price": 100.00,
        "photos": [],
        "amenities": [],
        "total_count": 5,
        "capacity": 2
    })
    assert room_resp.status_code == 201
    return {"hotel": test_hotel, "room": room_resp.json()}
