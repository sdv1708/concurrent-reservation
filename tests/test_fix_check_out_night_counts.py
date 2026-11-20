"""Tests for scripts/fix_check_out_night_counts.py.

The old code held one more row than the nights of a stay: the row on the
check-out date. These tests build that old state with Stay Inventory on the
range (check-in, check-out + 1 day), add the Booking, and run the fix.
Nothing commits, so the `db` fixture's rollback removes every row.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.booking import Booking
from app.models.enums import BookingStatusEnum
from app.models.hotel import Hotel
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.services import stay_inventory
from app.services.stay_inventory import Stay
from scripts.fix_check_out_night_counts import apply_fixes, check_rows

CUTOFF = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
BEFORE = datetime(2026, 11, 19, 12, 0)  # stored without a zone, in UTC
AFTER = datetime(2026, 11, 21, 12, 0)


def _day(n: int) -> date:
    return date.today() + timedelta(days=n)


@pytest.fixture
def room_type(db):
    user = User(email=f"fix-{uuid.uuid4().hex[:8]}@test.com", password_hash="x")
    db.add(user)
    db.flush()
    hotel = Hotel(name="Fix Hotel", city=f"fix-{uuid.uuid4().hex[:8]}", active=True, owner_id=user.id)
    db.add(hotel)
    db.flush()
    room = Room(hotel_id=hotel.id, type="STANDARD", base_price=Decimal("100.00"),
                total_count=5, capacity=2)
    db.add(room)
    db.flush()
    stay_inventory.ensure_rows(db, room.id)
    return room


def _old_booking(db, room, check_in, check_out, rooms, status, created_at=BEFORE):
    """Make a booking as the old code did: the check-out date is held too."""
    old_range = Stay(check_in, check_out + timedelta(days=1))
    stay_inventory.place_hold(db, room.id, old_range, rooms)
    if status in (BookingStatusEnum.CONFIRMED, BookingStatusEnum.CANCELLED):
        stay_inventory.book_hold(db, room.id, old_range, rooms)
    if status == BookingStatusEnum.CANCELLED:
        stay_inventory.release_booked(db, room.id, old_range, rooms)
    return _add_booking(db, room, check_in, check_out, rooms, status, created_at)


def _new_booking(db, room, check_in, check_out, rooms, status, created_at=AFTER):
    """Make a booking as the new code does: nights only."""
    stay = Stay(check_in, check_out)
    stay_inventory.place_hold(db, room.id, stay, rooms)
    if status == BookingStatusEnum.CONFIRMED:
        stay_inventory.book_hold(db, room.id, stay, rooms)
    return _add_booking(db, room, check_in, check_out, rooms, status, created_at)


def _add_booking(db, room, check_in, check_out, rooms, status, created_at):
    booking = Booking(hotel_id=room.hotel_id, room_id=room.id, user_id=room.hotel.owner_id,
                      rooms_count=rooms, check_in_date=check_in, check_out_date=check_out,
                      booking_status=status, amount=Decimal("1"), created_at=created_at)
    db.add(booking)
    db.flush()
    return booking


def _counts(db, room, night):
    row = db.execute(
        select(Inventory).where(Inventory.room_id == room.id, Inventory.date == night)
    ).scalar_one()
    return row.reserved_count, row.book_count


def _checks_for(db, room):
    return {c.night: c for c in check_rows(db, CUTOFF) if c.room_type_id == room.id}


def test_old_hold_check_out_count_is_released(db, room_type):
    _old_booking(db, room_type, _day(10), _day(12), 2, BookingStatusEnum.PAYMENTS_PENDING)
    assert _counts(db, room_type, _day(12)) == (2, 0)

    checks = _checks_for(db, room_type)
    assert checks[_day(12)].verdict == "fixable"
    assert apply_fixes(db, list(checks.values())) == 1

    assert _counts(db, room_type, _day(12)) == (0, 0)
    assert _counts(db, room_type, _day(11)) == (2, 0)  # the nights keep their hold


def test_old_confirmed_check_out_count_is_released(db, room_type):
    _old_booking(db, room_type, _day(10), _day(12), 1, BookingStatusEnum.CONFIRMED)

    apply_fixes(db, list(_checks_for(db, room_type).values()))

    assert _counts(db, room_type, _day(12)) == (0, 0)
    assert _counts(db, room_type, _day(11)) == (0, 1)


def test_old_hold_confirmed_by_new_code_is_released(db, room_type):
    """The new code moved the nights to booked. The check-out row keeps the hold."""
    booking = _old_booking(db, room_type, _day(10), _day(12), 1, BookingStatusEnum.RESERVED)
    stay_inventory.book_hold(db, room_type.id, Stay(_day(10), _day(12)), 1)
    booking.booking_status = BookingStatusEnum.CONFIRMED
    db.flush()

    apply_fixes(db, list(_checks_for(db, room_type).values()))

    assert _counts(db, room_type, _day(12)) == (0, 0)


def test_second_run_changes_nothing(db, room_type):
    _old_booking(db, room_type, _day(10), _day(12), 1, BookingStatusEnum.CONFIRMED)
    apply_fixes(db, list(_checks_for(db, room_type).values()))

    checks = list(_checks_for(db, room_type).values())
    assert [c.verdict for c in checks] == ["ok"]
    assert apply_fixes(db, checks) == 0
    assert _counts(db, room_type, _day(12)) == (0, 0)


def test_old_cancelled_booking_needs_no_fix(db, room_type):
    _old_booking(db, room_type, _day(10), _day(12), 1, BookingStatusEnum.CANCELLED)

    assert _checks_for(db, room_type)[_day(12)].verdict == "ok"


def test_new_bookings_are_not_changed(db, room_type):
    """A new booking whose stay has the old check-out date as a night keeps its count."""
    _old_booking(db, room_type, _day(10), _day(12), 1, BookingStatusEnum.RESERVED)
    _new_booking(db, room_type, _day(12), _day(14), 2, BookingStatusEnum.CONFIRMED)
    assert _counts(db, room_type, _day(12)) == (1, 2)

    checks = _checks_for(db, room_type)
    assert set(checks) == {_day(12)}  # the new booking's check-out date is not checked
    apply_fixes(db, list(checks.values()))

    assert _counts(db, room_type, _day(12)) == (0, 2)
    assert _counts(db, room_type, _day(14)) == (0, 0)


def test_mismatch_is_reported_and_not_changed(db, room_type):
    """An extra count that old bookings do not explain stays as it is."""
    _old_booking(db, room_type, _day(10), _day(12), 1, BookingStatusEnum.CONFIRMED)
    # A stray booked room on the check-out date, for example from a double confirm.
    stay_inventory.place_hold(db, room_type.id, Stay(_day(12), _day(13)), 1)
    stay_inventory.book_hold(db, room_type.id, Stay(_day(12), _day(13)), 1)

    checks = _checks_for(db, room_type)
    assert checks[_day(12)].verdict == "mismatch"
    assert apply_fixes(db, list(checks.values())) == 0
    assert _counts(db, room_type, _day(12)) == (0, 2)


def test_one_snapshot_setting_is_a_no_op_on_sqlite(db, room_type):
    from scripts.fix_check_out_night_counts import use_one_snapshot

    _old_booking(db, room_type, _day(10), _day(12), 1, BookingStatusEnum.RESERVED)
    use_one_snapshot(db)
    assert apply_fixes(db, list(_checks_for(db, room_type).values())) == 1
