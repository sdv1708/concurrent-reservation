"""Concurrency test for Stay Inventory on a real Postgres database.

SQLite leaves out SELECT ... FOR UPDATE, so only Postgres can show that two
concurrent holds on the last available room do not both succeed.

Opt in: set TEST_DATABASE_URL to a Postgres database that the test can
write to, for example postgresql://user:password@localhost:5432/test_db.
The test creates the tables if they do not exist and deletes its own rows
at the end.
"""
import os
import threading
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.hotel import Hotel
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.services import stay_inventory
from app.services.stay_inventory import Stay, StayUnavailableError

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
]


@pytest.fixture
def pg_sessions():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    engine.dispose()


def test_two_concurrent_holds_on_last_room_one_succeeds(pg_sessions):
    stay = Stay(date.today() + timedelta(days=10), date.today() + timedelta(days=12))

    with pg_sessions() as setup:
        user = User(email=f"pg-{uuid.uuid4().hex[:8]}@test.com", password_hash="x")
        setup.add(user)
        setup.flush()
        hotel = Hotel(name="PG Hotel", city=f"pg-{uuid.uuid4().hex[:8]}", active=True, owner_id=user.id)
        setup.add(hotel)
        setup.flush()
        room = Room(hotel_id=hotel.id, type="STANDARD", base_price=Decimal("100.00"),
                    total_count=1, capacity=2)
        setup.add(room)
        setup.flush()
        stay_inventory.ensure_rows(setup, room.id)
        setup.commit()
        user_id, hotel_id, room_id = user.id, hotel.id, room.id

    barrier = threading.Barrier(2)
    results: list[str] = []
    results_lock = threading.Lock()

    def try_hold():
        with pg_sessions() as session:
            barrier.wait()
            try:
                stay_inventory.place_hold(session, room_id, stay, 1)
                # Keep the row locks for a moment, so the other thread must wait on them.
                time.sleep(0.5)
                session.commit()
                outcome = "held"
            except StayUnavailableError:
                session.rollback()
                outcome = "unavailable"
            except Exception as exc:  # noqa: BLE001 - report any other failure
                session.rollback()
                outcome = f"error: {exc!r}"
            with results_lock:
                results.append(outcome)

    threads = [threading.Thread(target=try_hold) for _ in range(2)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert sorted(results) == ["held", "unavailable"]
        with pg_sessions() as check:
            counts = check.execute(
                select(Inventory.reserved_count)
                .where(Inventory.room_id == room_id,
                       Inventory.date >= stay.check_in, Inventory.date < stay.check_out)
            ).scalars().all()
        assert counts == [1, 1]
    finally:
        with pg_sessions() as cleanup:
            cleanup.execute(delete(Inventory).where(Inventory.room_id == room_id))
            cleanup.execute(delete(Room).where(Room.id == room_id))
            cleanup.execute(delete(Hotel).where(Hotel.id == hotel_id))
            cleanup.execute(delete(User).where(User.id == user_id))
            cleanup.commit()
