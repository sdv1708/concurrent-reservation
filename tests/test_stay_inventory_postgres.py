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


def test_check_out_fix_does_not_act_on_counts_changed_during_the_run(pg_sessions):
    """A confirm that commits after the fix script reads its snapshot must not
    make the script release the legitimate booked room."""
    from datetime import datetime, timezone

    from sqlalchemy.exc import DBAPIError

    from app.models.booking import Booking
    from app.models.enums import BookingStatusEnum
    from scripts.fix_check_out_night_counts import (
        apply_fixes, check_rows, is_serialization_failure, use_one_snapshot,
    )

    cutoff = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    night = date.today() + timedelta(days=20)  # D: the old booking's check-out date

    with pg_sessions() as setup:
        user = User(email=f"pg-{uuid.uuid4().hex[:8]}@test.com", password_hash="x")
        setup.add(user)
        setup.flush()
        hotel = Hotel(name="PG Fix Hotel", city=f"pg-{uuid.uuid4().hex[:8]}", active=True, owner_id=user.id)
        setup.add(hotel)
        setup.flush()
        room = Room(hotel_id=hotel.id, type="STANDARD", base_price=Decimal("100.00"),
                    total_count=5, capacity=2)
        setup.add(room)
        setup.flush()
        stay_inventory.ensure_rows(setup, room.id)

        # Old booking: the old code also held its check-out date D.
        stay_inventory.place_hold(setup, room.id, Stay(night - timedelta(days=2), night + timedelta(days=1)), 1)
        old = Booking(hotel_id=hotel.id, room_id=room.id, user_id=user.id, rooms_count=1,
                      check_in_date=night - timedelta(days=2), check_out_date=night,
                      booking_status=BookingStatusEnum.RESERVED, amount=Decimal("1"),
                      created_at=datetime(2026, 11, 19, 12, 0))
        # New booking: D is a night of its stay.
        stay_inventory.place_hold(setup, room.id, Stay(night, night + timedelta(days=2)), 1)
        new = Booking(hotel_id=hotel.id, room_id=room.id, user_id=user.id, rooms_count=1,
                      check_in_date=night, check_out_date=night + timedelta(days=2),
                      booking_status=BookingStatusEnum.PAYMENTS_PENDING, amount=Decimal("1"),
                      created_at=datetime(2026, 11, 21, 12, 0))
        setup.add_all([old, new])
        setup.commit()
        user_id, hotel_id, room_id, new_id = user.id, hotel.id, room.id, new.id

    def counts_on_night():
        with pg_sessions() as check:
            row = check.execute(
                select(Inventory).where(Inventory.room_id == room_id, Inventory.date == night)
            ).scalar_one()
            return row.reserved_count, row.book_count

    try:
        script = pg_sessions()
        use_one_snapshot(script)
        checks = [c for c in check_rows(script, cutoff) if c.room_type_id == room_id]
        assert [(c.night, c.verdict) for c in checks] == [(night, "fixable")]

        # The new app confirms the new booking while the script runs.
        with pg_sessions() as app_session:
            booking = app_session.get(Booking, new_id, with_for_update=True)
            stay_inventory.book_hold(app_session, room_id, Stay(night, night + timedelta(days=2)), 1)
            booking.booking_status = BookingStatusEnum.CONFIRMED
            app_session.commit()

        with pytest.raises(DBAPIError) as raised:
            apply_fixes(script, checks)
        assert is_serialization_failure(raised.value)
        script.rollback()
        script.close()
        assert counts_on_night() == (1, 1)  # the confirmed booked room is still there

        # A second run reads the new state and removes only the old extra hold.
        with pg_sessions() as rerun:
            use_one_snapshot(rerun)
            checks = [c for c in check_rows(rerun, cutoff) if c.room_type_id == room_id]
            assert apply_fixes(rerun, checks) == 1
            rerun.commit()
        assert counts_on_night() == (0, 1)
    finally:
        with pg_sessions() as cleanup:
            cleanup.execute(delete(Booking).where(Booking.room_id == room_id))
            cleanup.execute(delete(Inventory).where(Inventory.room_id == room_id))
            cleanup.execute(delete(Room).where(Room.id == room_id))
            cleanup.execute(delete(Hotel).where(Hotel.id == hotel_id))
            cleanup.execute(delete(User).where(User.id == user_id))
            cleanup.commit()
