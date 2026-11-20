"""Tests for the release of expired holds.

The booking services commit, so the rows that these tests make stay in
test.db until the session ends. Each test makes its own hotel and room type
and checks only its own bookings, because other tests leave holds behind.

A test makes a hold expire by moving its created_at 11 minutes back.
SQLite leaves out FOR UPDATE, so these tests run the two orders of the
webhook race one after the other. test_expired_holds_postgres.py runs them
at the same time on a real Postgres.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.booking import Booking
from app.models.enums import BookingStatusEnum
from app.models.hotel import Hotel
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.schemas.booking import BookingRequest
from app.services import booking_service, stay_inventory
from app.services.stay_inventory import Stay, StayUnavailableError


def _day(n: int) -> date:
    return date.today() + timedelta(days=n)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def guest(db):
    user = User(email=f"{_unique('guest')}@test.com", password_hash="x", name="Guest")
    db.add(user)
    db.commit()
    return user


def _room_type(db, owner, total_count) -> Room:
    hotel = Hotel(name=_unique("hotel"), city=_unique("city"), active=True, owner_id=owner.id)
    db.add(hotel)
    db.flush()
    room = Room(hotel_id=hotel.id, type="STANDARD", base_price=Decimal("100.00"),
                total_count=total_count, capacity=2)
    db.add(room)
    db.flush()
    stay_inventory.ensure_rows(db, room.id)
    db.commit()
    return room


STAY = Stay(_day(20), _day(22))


def _hold(db, user, room, stay=STAY, rooms=1, expired=False, session_id=None) -> int:
    """Place a hold through init_booking and return the booking id.

    With `expired`, the hold's payment window ran out 1 minute ago. With
    `session_id`, the booking is PAYMENTS_PENDING with that Stripe session.
    """
    booking = booking_service.init_booking(db, BookingRequest(
        hotel_id=room.hotel_id, room_id=room.id,
        check_in_date=stay.check_in, check_out_date=stay.check_out, rooms_count=rooms,
    ), user)
    if expired:
        booking.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=11)
    if session_id:
        booking.payment_session_id = session_id
        booking.booking_status = BookingStatusEnum.PAYMENTS_PENDING
    db.commit()
    return booking.id


def _status(db, booking_id) -> BookingStatusEnum:
    db.expire_all()
    return db.get(Booking, booking_id).booking_status


def _counts(db, room, stay=STAY) -> list[tuple[int, int]]:
    """(reserved_count, book_count) for each night of the stay."""
    db.expire_all()
    rows = db.execute(
        select(Inventory.reserved_count, Inventory.book_count)
        .where(Inventory.room_id == room.id,
               Inventory.date >= stay.check_in, Inventory.date < stay.check_out)
        .order_by(Inventory.date)
    ).all()
    return [tuple(r) for r in rows]


# ── Release ───────────────────────────────────────────────────────────────────

def test_release_frees_the_rooms_and_sets_expired(db, guest):
    room = _room_type(db, guest, total_count=5)
    booking_id = _hold(db, guest, room, rooms=2, expired=True)
    assert _counts(db, room) == [(2, 0), (2, 0)]

    booking_service.release_expired_holds(db)

    assert _status(db, booking_id) == BookingStatusEnum.EXPIRED
    assert _counts(db, room) == [(0, 0), (0, 0)]


@pytest.mark.parametrize("status", [BookingStatusEnum.GUESTS_ADDED, BookingStatusEnum.PAYMENTS_PENDING])
def test_release_covers_every_hold_state(db, guest, status):
    room = _room_type(db, guest, total_count=5)
    booking_id = _hold(db, guest, room, expired=True)
    db.get(Booking, booking_id).booking_status = status
    db.commit()

    assert booking_service.expire_hold(db, booking_id) is True
    assert _status(db, booking_id) == BookingStatusEnum.EXPIRED
    assert _counts(db, room) == [(0, 0), (0, 0)]


def test_second_release_changes_nothing(db, guest):
    room = _room_type(db, guest, total_count=5)
    # Hold the other booking first. Otherwise its init_booking releases the expired hold.
    other_id = _hold(db, guest, room)  # inside its window: keeps its hold
    booking_id = _hold(db, guest, room, expired=True)
    assert booking_service.expire_hold(db, booking_id) is True

    # A second release of the same booking, directly and through the job.
    # Neither may decrement reserved_count again.
    assert booking_service.expire_hold(db, booking_id) is False
    booking_service.release_expired_holds(db)

    assert _status(db, booking_id) == BookingStatusEnum.EXPIRED
    assert _status(db, other_id) == BookingStatusEnum.RESERVED
    assert _counts(db, room) == [(1, 0), (1, 0)]


def test_hold_inside_its_window_is_not_released(db, guest):
    room = _room_type(db, guest, total_count=5)
    booking_id = _hold(db, guest, room)

    assert booking_service.expire_hold(db, booking_id) is False
    booking_service.release_expired_holds(db)

    assert _status(db, booking_id) == BookingStatusEnum.RESERVED
    assert _counts(db, room) == [(1, 0), (1, 0)]


def test_job_releases_the_hold_at_the_end_of_the_window(db, guest):
    room = _room_type(db, guest, total_count=5)
    booking_id = _hold(db, guest, room)
    created = db.get(Booking, booking_id).created_at.replace(tzinfo=timezone.utc)

    booking_service.release_expired_holds(db, now=created + timedelta(minutes=9))
    assert _status(db, booking_id) == BookingStatusEnum.RESERVED

    booking_service.release_expired_holds(db, now=created + timedelta(minutes=10, seconds=1))
    assert _status(db, booking_id) == BookingStatusEnum.EXPIRED


def test_expired_booking_cannot_go_on_to_payment(db, guest):
    from fastapi import HTTPException

    room = _room_type(db, guest, total_count=5)
    booking_id = _hold(db, guest, room, expired=True)
    booking_service.expire_hold(db, booking_id)

    with pytest.raises(HTTPException) as exc:
        booking_service.initiate_payment(db, booking_id, guest)
    assert exc.value.status_code == 400
    assert _status(db, booking_id) == BookingStatusEnum.EXPIRED


# ── Lazy release in init_booking ──────────────────────────────────────────────

def test_new_hold_releases_an_expired_hold_that_blocks_it(db, guest):
    room = _room_type(db, guest, total_count=1)
    expired_id = _hold(db, guest, room, expired=True)

    # The stays share the night of day 21.
    new_stay = Stay(_day(21), _day(23))
    new_id = _hold(db, guest, room, stay=new_stay)

    assert _status(db, expired_id) == BookingStatusEnum.EXPIRED
    assert _status(db, new_id) == BookingStatusEnum.RESERVED
    assert _counts(db, room, Stay(_day(20), _day(23))) == [(0, 0), (1, 0), (1, 0)]


def test_new_hold_still_fails_when_the_blocking_hold_is_not_expired(db, guest):
    room = _room_type(db, guest, total_count=1)
    blocking_id = _hold(db, guest, room)

    with pytest.raises(StayUnavailableError):
        _hold(db, guest, room)
    db.rollback()
    assert _status(db, blocking_id) == BookingStatusEnum.RESERVED


def test_new_hold_leaves_expired_holds_on_other_nights(db, guest):
    room = _room_type(db, guest, total_count=1)
    expired_id = _hold(db, guest, room, expired=True)

    _hold(db, guest, room, stay=Stay(_day(30), _day(31)))

    # The job releases this hold. init_booking does not, because it does not block the new stay.
    assert _status(db, expired_id) == BookingStatusEnum.RESERVED


# ── Race with the Stripe webhook ──────────────────────────────────────────────

def test_webhook_first_then_release_changes_nothing(db, guest):
    """The webhook gets the booking lock first. It books the hold, even though
    the window ran out, because the hold still exists. The release then reads
    CONFIRMED and changes nothing."""
    room = _room_type(db, guest, total_count=1)
    session_id = _unique("sess")
    booking_id = _hold(db, guest, room, expired=True, session_id=session_id)

    booking_service.confirm_booking(db, session_id)
    assert booking_service.expire_hold(db, booking_id) is False
    booking_service.release_expired_holds(db)

    assert _status(db, booking_id) == BookingStatusEnum.CONFIRMED
    assert _counts(db, room) == [(0, 1), (0, 1)]


def test_release_first_then_webhook_holds_the_stay_again(db, guest):
    """The release gets the booking lock first. The webhook then reads EXPIRED,
    places a new hold for the stay, and books it."""
    room = _room_type(db, guest, total_count=1)
    session_id = _unique("sess")
    booking_id = _hold(db, guest, room, expired=True, session_id=session_id)

    assert booking_service.expire_hold(db, booking_id) is True
    assert _counts(db, room) == [(0, 0), (0, 0)]
    booking_service.confirm_booking(db, session_id)
    booking_service.confirm_booking(db, session_id)  # a repeated delivery

    assert _status(db, booking_id) == BookingStatusEnum.CONFIRMED
    assert _counts(db, room) == [(0, 1), (0, 1)]


@patch("app.services.booking_service.stripe.Refund.create")
@patch("app.services.booking_service.stripe.checkout.Session.retrieve")
@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_release_first_then_webhook_refunds_when_the_stay_is_taken(
    mock_event, mock_retrieve, mock_refund, db, client, guest
):
    """Another guest takes the released room before the payment arrives. The
    webhook route refunds the payment once and sets the booking to CANCELLED."""
    room = _room_type(db, guest, total_count=1)
    session_id = _unique("sess")
    booking_id = _hold(db, guest, room, expired=True, session_id=session_id)
    taker_id = _hold(db, guest, room)  # the lazy release frees the room first

    mock_event.return_value = {"type": "checkout.session.completed", "data": {"object": {"id": session_id}}}
    mock_retrieve.return_value = MagicMock(payment_intent="pi_late")

    for _ in range(2):  # Stripe can deliver the event twice
        r = client.post("/webhook/payment", headers={"Stripe-Signature": "t=1,v1=x"}, content=b"{}")
        assert r.status_code == 204

    mock_refund.assert_called_once_with(
        payment_intent="pi_late", idempotency_key=f"late-payment-refund-{booking_id}"
    )
    assert _status(db, booking_id) == BookingStatusEnum.CANCELLED
    assert _status(db, taker_id) == BookingStatusEnum.RESERVED
    assert _counts(db, room) == [(1, 0), (1, 0)]


@patch("app.services.booking_service.stripe.Refund.create")
@patch("app.services.booking_service.stripe.checkout.Session.retrieve")
def test_release_first_then_webhook_refunds_when_a_night_is_closed(mock_retrieve, mock_refund, db, guest):
    room = _room_type(db, guest, total_count=5)
    session_id = _unique("sess")
    booking_id = _hold(db, guest, room, expired=True, session_id=session_id)
    booking_service.expire_hold(db, booking_id)
    stay_inventory.change_nights(db, room.id, _day(21), _day(21), closed=True)
    db.commit()
    mock_retrieve.return_value = MagicMock(payment_intent="pi_closed")

    booking_service.confirm_booking(db, session_id)

    mock_refund.assert_called_once()
    assert _status(db, booking_id) == BookingStatusEnum.CANCELLED
    assert _counts(db, room) == [(0, 0), (0, 0)]
