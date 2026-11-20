"""Stay Inventory: the one module that owns every rule about Inventory rows.

An Inventory row holds the counts for one room type on one night:
  total_count    rooms of the room type
  reserved_count rooms in a hold (placed before payment)
  book_count     booked rooms (payment received)
  closed         the manager stopped new holds on this night

Available rooms = total_count - book_count - reserved_count.

Rules that this module owns:
  * A stay covers each night from the check-in date up to, but not
    including, the check-out date. See `Stay`.
  * Every operation that changes counts locks the rows of the stay with
    SELECT ... FOR UPDATE ORDER BY date. Two overlapping stays thus lock
    their shared nights in the same order and cannot deadlock.
  * A count never goes below zero. A change that would do so raises
    `InventoryCountError`, because it is a bug in the caller.
  * A closed night stops new holds only. Existing holds and booked rooms
    on a closed night stay valid.

Transactions: this module never commits. It adds and flushes only. The
caller that owns the operation commits once.

Trust: this module does no ownership checks. The caller does them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Subquery

from app.models.inventory import Inventory
from app.models.room import Room

# Row generation keeps rows for this many nights, from today onward.
WINDOW_NIGHTS = 365


# ── Errors ────────────────────────────────────────────────────────────────────

class StayUnavailableError(Exception):
    """The room type does not have enough available rooms on every night of
    the stay, or one night of the stay is closed or has no row."""


class InventoryCountError(Exception):
    """A change would make a count go below zero, or a night of the stay has
    no row. This is a bug in the caller, not a guest error."""


# ── Value types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Stay:
    """The nights a guest occupies: from `check_in` up to, but not including,
    `check_out`. A stay from 2026-08-05 to 2026-08-07 is 2 nights."""
    check_in: date
    check_out: date

    def __post_init__(self):
        if self.check_out <= self.check_in:
            raise ValueError(
                f"check-out date {self.check_out} must be after check-in date {self.check_in}"
            )

    @property
    def night_count(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def nights(self) -> list[date]:
        return [self.check_in + timedelta(days=i) for i in range(self.night_count)]


@dataclass(frozen=True)
class InventoryNight:
    """A read-only copy of the Inventory row of one room type on one night.

    The pricing chain reads `date`, `price`, `surge_factor`, `total_count`,
    and `book_count`. The admin routes show all fields.
    """
    id: int
    date: date
    total_count: int
    book_count: int
    reserved_count: int
    price: Decimal
    surge_factor: Decimal
    closed: bool

    @property
    def available(self) -> int:
        return self.total_count - self.book_count - self.reserved_count

    @classmethod
    def _from_row(cls, row: Inventory) -> "InventoryNight":
        return cls(
            id=row.id,
            date=row.date,
            total_count=row.total_count,
            book_count=row.book_count,
            reserved_count=row.reserved_count,
            price=row.price,
            surge_factor=row.surge_factor,
            closed=row.closed,
        )


# ── Private helpers ───────────────────────────────────────────────────────────

def _available_expr():
    return Inventory.total_count - Inventory.book_count - Inventory.reserved_count


def _lock_rows(db: Session, room_type_id: int, first_night: date, end: date) -> list[Inventory]:
    """Lock and return the rows of the room type on nights first_night <= night < end.

    ORDER BY date makes every caller lock rows in the same order.
    SQLAlchemy leaves FOR UPDATE out on SQLite, which locks the whole
    database file on write instead.
    """
    return list(db.execute(
        select(Inventory)
        .where(
            Inventory.room_id == room_type_id,
            Inventory.date >= first_night,
            Inventory.date < end,
        )
        .order_by(Inventory.date)
        .with_for_update()
    ).scalars().all())


def _lock_stay(db: Session, room_type_id: int, stay: Stay) -> list[Inventory]:
    return _lock_rows(db, room_type_id, stay.check_in, stay.check_out)


def _check_room_count(rooms: int) -> None:
    if rooms < 1:
        raise ValueError(f"room count must be 1 or more, got {rooms}")


def _lock_stay_for_change(db: Session, room_type_id: int, stay: Stay, rooms: int) -> list[Inventory]:
    """Lock the rows of the stay for a release or a hold-to-booked change.

    Raises InventoryCountError if a night of the stay has no row.
    """
    _check_room_count(rooms)
    rows = _lock_stay(db, room_type_id, stay)
    if len(rows) != stay.night_count:
        raise InventoryCountError(
            f"room type {room_type_id} has {len(rows)} rows for a stay of "
            f"{stay.night_count} nights from {stay.check_in}"
        )
    return rows


def _require_at_least(rows: list[Inventory], field: str, rooms: int) -> None:
    for row in rows:
        current = getattr(row, field)
        if current < rooms:
            raise InventoryCountError(
                f"cannot remove {rooms} from {field}={current} for room type "
                f"{row.room_id} on {row.date}"
            )


# ── Holds and booked rooms ────────────────────────────────────────────────────

def place_hold(db: Session, room_type_id: int, stay: Stay, rooms: int) -> list[InventoryNight]:
    """Place a hold on `rooms` rooms of the room type for each night of the stay.

    Increments `reserved_count` on each night. Returns the held nights in date
    order, with the price fields that the pricing chain reads.

    Raises:
        StayUnavailableError: a night of the stay has no row, is closed, or has
            fewer than `rooms` available rooms.
        ValueError: `rooms` is less than 1.
    """
    _check_room_count(rooms)
    rows = _lock_stay(db, room_type_id, stay)

    if len(rows) != stay.night_count:
        raise StayUnavailableError(
            f"Room type {room_type_id} has no inventory for some nights "
            f"from {stay.check_in} to {stay.check_out}"
        )
    for row in rows:
        if row.closed:
            raise StayUnavailableError(f"Room type {room_type_id} is closed on {row.date}")
        available = row.total_count - row.book_count - row.reserved_count
        if available < rooms:
            raise StayUnavailableError(
                f"Room type {room_type_id} has {available} available rooms on "
                f"{row.date}, {rooms} requested"
            )

    for row in rows:
        row.reserved_count += rooms
    db.flush()
    return [InventoryNight._from_row(row) for row in rows]


def book_hold(db: Session, room_type_id: int, stay: Stay, rooms: int) -> None:
    """Turn a hold into booked rooms: move `rooms` from `reserved_count` to
    `book_count` on each night of the stay.

    Raises:
        InventoryCountError: a night has no row, or `reserved_count` < `rooms`.
    """
    rows = _lock_stay_for_change(db, room_type_id, stay, rooms)
    _require_at_least(rows, "reserved_count", rooms)
    for row in rows:
        row.reserved_count -= rooms
        row.book_count += rooms
    db.flush()


def release_hold(db: Session, room_type_id: int, stay: Stay, rooms: int) -> None:
    """Release a hold: decrement `reserved_count` by `rooms` on each night.

    Raises:
        InventoryCountError: a night has no row, or `reserved_count` < `rooms`.
    """
    rows = _lock_stay_for_change(db, room_type_id, stay, rooms)
    _require_at_least(rows, "reserved_count", rooms)
    for row in rows:
        row.reserved_count -= rooms
    db.flush()


def release_booked(db: Session, room_type_id: int, stay: Stay, rooms: int) -> None:
    """Release booked rooms: decrement `book_count` by `rooms` on each night.

    Raises:
        InventoryCountError: a night has no row, or `book_count` < `rooms`.
    """
    rows = _lock_stay_for_change(db, room_type_id, stay, rooms)
    _require_at_least(rows, "book_count", rooms)
    for row in rows:
        row.book_count -= rooms
    db.flush()


# ── Row generation ────────────────────────────────────────────────────────────

def _insert_ignoring_duplicates(db: Session, values: list[dict]) -> None:
    """INSERT ... ON CONFLICT DO NOTHING on the unique_hotel_room_date columns.

    A concurrent run that inserts the same night first makes this insert skip
    that night, so the unique constraint is never violated.
    """
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise NotImplementedError(f"row generation does not support the {dialect} dialect")

    stmt = insert(Inventory).on_conflict_do_nothing(
        index_elements=["hotel_id", "room_id", "date"]
    )
    db.execute(stmt, values)


def ensure_rows(db: Session, room_type_id: int) -> None:
    """Make sure that the room type has a row for each night from today up to,
    but not including, today + WINDOW_NIGHTS.

    New rows copy `base_price` and `total_count` from the room type and `city`
    from its hotel. Existing rows do not change. A second run adds nothing.
    Two concurrent runs do not violate the unique_hotel_room_date constraint.

    The caller must flush a new room type before it calls this function.
    """
    room = db.get(Room, room_type_id)
    if room is None:
        raise ValueError(f"room type {room_type_id} does not exist")

    first_night = date.today()
    end = first_night + timedelta(days=WINDOW_NIGHTS)
    existing = set(db.execute(
        select(Inventory.date).where(
            Inventory.room_id == room_type_id,
            Inventory.date >= first_night,
            Inventory.date < end,
        )
    ).scalars().all())

    values = [
        dict(
            hotel_id=room.hotel_id,
            room_id=room.id,
            date=night,
            price=room.base_price,
            total_count=room.total_count,
            surge_factor=1,
            book_count=0,
            reserved_count=0,
            closed=False,
            city=room.hotel.city,
        )
        for night in (first_night + timedelta(days=i) for i in range(WINDOW_NIGHTS))
        if night not in existing
    ]
    if values:
        _insert_ignoring_duplicates(db, values)
    db.flush()


# ── Admin changes ─────────────────────────────────────────────────────────────

def list_nights(db: Session, room_type_id: int) -> list[InventoryNight]:
    """Return every row of the room type in date order."""
    rows = db.execute(
        select(Inventory).where(Inventory.room_id == room_type_id).order_by(Inventory.date)
    ).scalars().all()
    return [InventoryNight._from_row(row) for row in rows]


def change_nights(
    db: Session,
    room_type_id: int,
    first_night: date,
    last_night: date,
    *,
    closed: Optional[bool] = None,
    surge_factor: Optional[Decimal] = None,
) -> list[InventoryNight]:
    """Close or open nights, and set the surge factor, for each night from
    `first_night` through `last_night`. Both dates are included.

    A None argument leaves that field as it is. Closing a night does not
    change existing holds or booked rooms.
    """
    rows = _lock_rows(db, room_type_id, first_night, last_night + timedelta(days=1))
    for row in rows:
        if closed is not None:
            row.closed = closed
        if surge_factor is not None:
            row.surge_factor = surge_factor
    db.flush()
    return [InventoryNight._from_row(row) for row in rows]


# ── Hotel search ──────────────────────────────────────────────────────────────

def available_hotels(city: str, stay: Stay, rooms: int) -> Subquery:
    """Return a subquery of the hotels in `city` with availability for the stay.

    A hotel has availability when at least one of its room types has at least
    `rooms` available rooms, and is not closed, on every night of the stay.

    Columns:
        hotel_id:  the hotel.
        min_price: the lowest raw `price` over the nights of the room types
                   that have availability.

    The caller adds hotel filters, joins, and paging.
    """
    _check_room_count(rooms)
    per_room_type = (
        select(
            Inventory.hotel_id.label("hotel_id"),
            func.min(Inventory.price).label("min_price"),
        )
        .where(
            Inventory.city == city,
            Inventory.date >= stay.check_in,
            Inventory.date < stay.check_out,
            Inventory.closed == False,  # noqa: E712
            _available_expr() >= rooms,
        )
        .group_by(Inventory.hotel_id, Inventory.room_id)
        .having(func.count(Inventory.id) == stay.night_count)
        .subquery()
    )
    return (
        select(
            per_room_type.c.hotel_id,
            func.min(per_room_type.c.min_price).label("min_price"),
        )
        .group_by(per_room_type.c.hotel_id)
        .subquery()
    )
