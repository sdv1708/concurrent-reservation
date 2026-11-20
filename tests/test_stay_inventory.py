"""Tests for app.services.stay_inventory.

These tests call the module directly with the `db` fixture. The module never
commits, so the fixture's rollback removes every row that a test creates.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.hotel import Hotel
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.pricing.pricing_service import calculate_dynamic_price, calculate_total_price
from app.services import stay_inventory
from app.services.stay_inventory import InventoryCountError, Stay, StayUnavailableError


def _day(n: int) -> date:
    return date.today() + timedelta(days=n)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def owner(db):
    user = User(email=f"{_unique('owner')}@test.com", password_hash="x", name="Owner")
    db.add(user)
    db.flush()
    return user


def _make_hotel(db, owner, city=None, active=True) -> Hotel:
    hotel = Hotel(name=_unique("hotel"), city=city or _unique("city"), active=active, owner_id=owner.id)
    db.add(hotel)
    db.flush()
    return hotel


def _make_room_type(db, hotel, total_count=5, base_price="100.00", with_rows=True) -> Room:
    room = Room(hotel_id=hotel.id, type="STANDARD", base_price=Decimal(base_price),
                total_count=total_count, capacity=2)
    db.add(room)
    db.flush()
    if with_rows:
        stay_inventory.ensure_rows(db, room.id)
    return room


def _row(db, room_type_id, night) -> Inventory:
    return db.execute(
        select(Inventory).where(Inventory.room_id == room_type_id, Inventory.date == night)
    ).scalar_one()


def _row_count(db, room_type_id) -> int:
    return db.execute(
        select(func.count()).select_from(Inventory).where(Inventory.room_id == room_type_id)
    ).scalar_one()


def _search(db, city, stay, rooms) -> set[int]:
    sub = stay_inventory.available_hotels(city, stay, rooms)
    return {hotel_id for hotel_id, _ in db.execute(select(sub.c.hotel_id, sub.c.min_price)).all()}


# ── Stay ──────────────────────────────────────────────────────────────────────

def test_stay_excludes_check_out_date():
    stay = Stay(date(2026, 8, 5), date(2026, 8, 7))
    assert stay.night_count == 2
    assert stay.nights == [date(2026, 8, 5), date(2026, 8, 6)]


def test_stay_needs_check_out_after_check_in():
    with pytest.raises(ValueError):
        Stay(date(2026, 8, 5), date(2026, 8, 5))


# ── Holds ─────────────────────────────────────────────────────────────────────

def test_two_night_stay_holds_exactly_two_nights(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    stay = Stay(_day(20), _day(22))

    held = stay_inventory.place_hold(db, room.id, stay, 2)

    assert [n.date for n in held] == [_day(20), _day(21)]
    assert _row(db, room.id, _day(20)).reserved_count == 2
    assert _row(db, room.id, _day(21)).reserved_count == 2
    assert _row(db, room.id, _day(22)).reserved_count == 0  # the check-out date is not a night

    price = calculate_total_price(held)
    assert price == calculate_dynamic_price(held[0]) + calculate_dynamic_price(held[1])
    assert price > 0


def test_hold_fails_when_one_night_has_too_few_available_rooms(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner), total_count=2)
    stay_inventory.place_hold(db, room.id, Stay(_day(11), _day(12)), 2)

    with pytest.raises(StayUnavailableError):
        stay_inventory.place_hold(db, room.id, Stay(_day(10), _day(12)), 1)

    assert _row(db, room.id, _day(10)).reserved_count == 0


def test_hold_fails_outside_the_inventory_window(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    end = stay_inventory.WINDOW_NIGHTS
    with pytest.raises(StayUnavailableError):
        stay_inventory.place_hold(db, room.id, Stay(_day(end - 1), _day(end + 1)), 1)


def test_hold_fails_on_closed_night_and_close_keeps_existing_hold(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    stay = Stay(_day(10), _day(12))
    stay_inventory.place_hold(db, room.id, stay, 1)

    closed = stay_inventory.change_nights(db, room.id, _day(11), _day(11), closed=True)

    assert [n.date for n in closed] == [_day(11)]
    assert _row(db, room.id, _day(11)).reserved_count == 1
    with pytest.raises(StayUnavailableError):
        stay_inventory.place_hold(db, room.id, stay, 1)

    # The existing hold on the closed night can still become booked.
    stay_inventory.book_hold(db, room.id, stay, 1)
    assert _row(db, room.id, _day(11)).book_count == 1


def test_hold_needs_at_least_one_room(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    with pytest.raises(ValueError):
        stay_inventory.place_hold(db, room.id, Stay(_day(10), _day(12)), 0)


# ── Booked rooms and releases ─────────────────────────────────────────────────

def test_book_hold_moves_count_from_reserved_to_booked(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    stay = Stay(_day(10), _day(12))
    stay_inventory.place_hold(db, room.id, stay, 3)

    stay_inventory.book_hold(db, room.id, stay, 2)

    for night in stay.nights:
        row = _row(db, room.id, night)
        assert (row.reserved_count, row.book_count) == (1, 2)


def test_release_hold_and_release_booked(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    stay = Stay(_day(10), _day(12))
    stay_inventory.place_hold(db, room.id, stay, 3)
    stay_inventory.book_hold(db, room.id, stay, 2)

    stay_inventory.release_hold(db, room.id, stay, 1)
    stay_inventory.release_booked(db, room.id, stay, 2)

    for night in stay.nights:
        row = _row(db, room.id, night)
        assert (row.reserved_count, row.book_count) == (0, 0)


def test_release_more_than_held_raises(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    stay = Stay(_day(10), _day(12))
    stay_inventory.place_hold(db, room.id, stay, 1)

    with pytest.raises(InventoryCountError):
        stay_inventory.release_hold(db, room.id, stay, 2)
    with pytest.raises(InventoryCountError):
        stay_inventory.book_hold(db, room.id, stay, 2)

    assert _row(db, room.id, _day(10)).reserved_count == 1


def test_release_more_than_booked_raises(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    stay = Stay(_day(10), _day(12))
    stay_inventory.place_hold(db, room.id, stay, 1)
    stay_inventory.book_hold(db, room.id, stay, 1)

    with pytest.raises(InventoryCountError):
        stay_inventory.release_booked(db, room.id, stay, 2)

    assert _row(db, room.id, _day(10)).book_count == 1


# ── Row generation ────────────────────────────────────────────────────────────

def test_ensure_rows_copies_room_type_and_hotel_fields(db, owner):
    hotel = _make_hotel(db, owner)
    room = _make_room_type(db, hotel, total_count=7, base_price="150.00")

    assert _row_count(db, room.id) == stay_inventory.WINDOW_NIGHTS
    row = _row(db, room.id, _day(0))
    assert (row.price, row.total_count, row.city) == (Decimal("150.00"), 7, hotel.city)
    assert _row(db, room.id, _day(stay_inventory.WINDOW_NIGHTS - 1)) is not None


def test_ensure_rows_second_run_adds_no_rows(db, owner):
    room = _make_room_type(db, _make_hotel(db, owner))
    stay_inventory.place_hold(db, room.id, Stay(_day(10), _day(11)), 1)

    stay_inventory.ensure_rows(db, room.id)

    assert _row_count(db, room.id) == stay_inventory.WINDOW_NIGHTS
    assert _row(db, room.id, _day(10)).reserved_count == 1  # existing rows do not change


# ── Hotel search ──────────────────────────────────────────────────────────────

def test_search_needs_one_room_type_to_cover_every_night(db, owner):
    city = _unique("city")
    stay = Stay(_day(10), _day(12))

    # Two room types. Each one has a free room on one night of the stay only.
    split = _make_hotel(db, owner, city=city)
    room_a = _make_room_type(db, split, total_count=1)
    room_b = _make_room_type(db, split, total_count=1)
    stay_inventory.place_hold(db, room_a.id, Stay(_day(11), _day(12)), 1)
    stay_inventory.place_hold(db, room_b.id, Stay(_day(10), _day(11)), 1)

    # One room type that is free on every night of the stay.
    whole = _make_hotel(db, owner, city=city)
    _make_room_type(db, whole, total_count=1)

    assert _search(db, city, stay, 1) == {whole.id}


def test_search_skips_closed_nights_and_reports_min_price(db, owner):
    city = _unique("city")
    stay = Stay(_day(10), _day(12))
    hotel = _make_hotel(db, owner, city=city)
    cheap = _make_room_type(db, hotel, base_price="80.00")
    _make_room_type(db, hotel, base_price="120.00")

    sub = stay_inventory.available_hotels(city, stay, 1)
    assert db.execute(select(sub.c.min_price)).scalar_one() == Decimal("80.00")

    stay_inventory.change_nights(db, cheap.id, _day(11), _day(11), closed=True)
    sub = stay_inventory.available_hotels(city, stay, 1)
    assert db.execute(select(sub.c.min_price)).scalar_one() == Decimal("120.00")


def test_search_filters_by_city(db, owner):
    city, other_city = _unique("city"), _unique("city")
    stay = Stay(_day(10), _day(12))
    here = _make_hotel(db, owner, city=city)
    _make_room_type(db, here)
    _make_room_type(db, _make_hotel(db, owner, city=other_city))

    assert _search(db, city, stay, 1) == {here.id}
