"""Race test for the release of an expired hold and the Stripe webhook, on a
real Postgres database.

SQLite leaves out SELECT ... FOR UPDATE, so only Postgres can show that a
release and a confirm of the same booking, at the same time, do not both act
on it. Whichever one gets the booking lock first, the end state must be the
same: the booking is CONFIRMED, book_count is 1, and reserved_count is 0.

Opt in: set TEST_DATABASE_URL, as for test_stay_inventory_postgres.py.
"""
import os
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.booking import Booking
from app.models.enums import BookingStatusEnum
from app.models.hotel import Hotel
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.schemas.booking import BookingRequest
from app.services import booking_service, stay_inventory

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
ROUNDS = 10

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


def test_release_and_webhook_at_the_same_time_end_confirmed(pg_sessions):
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

    try:
        for i in range(ROUNDS):
            # Each round uses its own one-night stay on the room type's single room.
            night = date.today() + timedelta(days=10 + i)
            session_id = f"sess-pg-{uuid.uuid4().hex}"
            with pg_sessions() as s:
                booking = booking_service.init_booking(s, BookingRequest(
                    hotel_id=hotel_id, room_id=room_id, check_in_date=night,
                    check_out_date=night + timedelta(days=1), rooms_count=1,
                ), s.get(User, user_id))
                booking.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=11)
                booking.payment_session_id = session_id
                booking.booking_status = BookingStatusEnum.PAYMENTS_PENDING
                s.commit()
                booking_id = booking.id

            barrier = threading.Barrier(2)
            errors: list[str] = []

            def run(action):
                with pg_sessions() as session:
                    barrier.wait()
                    try:
                        action(session)
                    except Exception as exc:  # noqa: BLE001 - report any failure
                        session.rollback()
                        errors.append(repr(exc))

            threads = [
                threading.Thread(target=run, args=(lambda s: booking_service.expire_hold(s, booking_id),)),
                threading.Thread(target=run, args=(lambda s: booking_service.confirm_booking(s, session_id),)),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            assert errors == []
            with pg_sessions() as check:
                status = check.get(Booking, booking_id).booking_status
                counts = check.execute(
                    select(Inventory.reserved_count, Inventory.book_count)
                    .where(Inventory.room_id == room_id, Inventory.date == night)
                ).one()
            assert status == BookingStatusEnum.CONFIRMED
            assert tuple(counts) == (0, 1)
    finally:
        with pg_sessions() as cleanup:
            cleanup.execute(delete(Booking).where(Booking.room_id == room_id))
            cleanup.execute(delete(Inventory).where(Inventory.room_id == room_id))
            cleanup.execute(delete(Room).where(Room.id == room_id))
            cleanup.execute(delete(Hotel).where(Hotel.id == hotel_id))
            cleanup.execute(delete(User).where(User.id == user_id))
            cleanup.commit()
