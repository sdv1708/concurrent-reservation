"""One-off fix: remove the extra count on the check-out date of old bookings.

Before the Stay Inventory change, init_booking treated the check-out date as
a night of the stay. Each booking thus held one more row than its nights:
the row on its check-out date. The old code then kept that extra count:
  * a hold (RESERVED, GUESTS_ADDED, PAYMENTS_PENDING) has +rooms_count in
    reserved_count on its check-out date.
  * a CONFIRMED booking has +rooms_count in book_count on its check-out date.
  * an EXPIRED booking keeps +rooms_count in reserved_count on its
    check-out date. The new release frees only the nights of the stay.
  * a CANCELLED booking has no extra count. The old cancel released it.
    If the new code cancelled an old CONFIRMED booking, its extra book_count
    stays. The script reports that row as a mismatch.

The new code releases only the nights of a stay. Without this fix, the extra
count on each check-out date never goes away.

How the script decides, for each (room type, check-out date) of an old booking:
  1. Expected counts: the sum of rooms_count over the bookings that have this
     date as a night under the new rule (check-in <= date < check-out).
     Holds count to reserved_count. CONFIRMED bookings count to book_count.
  2. Extra = actual count - expected count, for reserved and for booked.
  3. The row is:
       ok        both extras are 0. Nothing to do. A second run finds this.
       fixable   both extras are 0 or more, and their sum is equal to the
                 rooms_count of the old bookings that check out on this date.
       mismatch  any other result. The script reports the row and does not
                 change it. Fix these rows by hand.

A fixable row is fixed through stay_inventory.release_hold and
release_booked on the one-night stay (date, date + 1). The script commits
once, after all rows. It never changes a mismatch row.

Consistent reads: on Postgres, the script runs in one REPEATABLE READ
transaction. It reads every Booking and Inventory row from the same snapshot,
so a booking that the new app confirms or cancels during the run cannot make
the script release a legitimate count. If such a write changed a row that
the script then tries to fix, Postgres raises a serialization error on the
row lock. The script then rolls back every change and exits with code 1.
Run it again.

Run it when no old app version writes to the database: stop the old version,
deploy the new version, then run this script. The new version can keep
serving traffic. Old bookings are the bookings created before
--created-before. Use the time the old version stopped.

Usage (from the repository root):
  python -m scripts.fix_check_out_night_counts --created-before 2026-11-20T09:00:00+00:00
  python -m scripts.fix_check_out_night_counts --created-before 2026-11-20T09:00:00+00:00 --apply

Without --apply, the script changes nothing and only prints its report.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.enums import BookingStatusEnum
from app.services import stay_inventory
from app.services.stay_inventory import Stay

HELD = (
    BookingStatusEnum.RESERVED,
    BookingStatusEnum.GUESTS_ADDED,
    BookingStatusEnum.PAYMENTS_PENDING,
)


@dataclass(frozen=True)
class RowCheck:
    room_type_id: int
    night: date
    actual_reserved: int
    actual_booked: int
    expected_reserved: int
    expected_booked: int
    old_rooms: int  # rooms_count of old bookings that check out on this date
    missing_row: bool = False

    @property
    def extra_reserved(self) -> int:
        return self.actual_reserved - self.expected_reserved

    @property
    def extra_booked(self) -> int:
        return self.actual_booked - self.expected_booked

    @property
    def verdict(self) -> str:
        if self.missing_row:
            return "mismatch"
        if self.extra_reserved == 0 and self.extra_booked == 0:
            return "ok"
        if (self.extra_reserved >= 0 and self.extra_booked >= 0
                and self.extra_reserved + self.extra_booked == self.old_rooms):
            return "fixable"
        return "mismatch"


def _as_utc(value: datetime) -> datetime:
    # Booking.created_at is stored without a time zone, in UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def check_rows(db: Session, created_before: datetime) -> list[RowCheck]:
    """Return one RowCheck for each (room type, check-out date) of an old booking."""
    created_before = _as_utc(created_before)
    bookings = db.execute(select(Booking)).scalars().all()

    by_room_type: dict[int, list[Booking]] = defaultdict(list)
    for b in bookings:
        by_room_type[b.room_id].append(b)

    # Check the check-out row of every old booking. A CANCELLED old booking
    # adds no expected extra, so an extra count on its row shows as a mismatch.
    old_rooms: dict[tuple[int, date], int] = defaultdict(int)
    for b in bookings:
        if _as_utc(b.created_at) < created_before:
            extra = 0 if b.booking_status == BookingStatusEnum.CANCELLED else b.rooms_count
            old_rooms[(b.room_id, b.check_out_date)] += extra

    checks = []
    nights_by_room_type: dict[int, dict] = {}
    for (room_type_id, night), rooms in sorted(old_rooms.items()):
        expected_reserved = expected_booked = 0
        for b in by_room_type[room_type_id]:
            if b.check_in_date <= night < b.check_out_date:
                if b.booking_status in HELD:
                    expected_reserved += b.rooms_count
                elif b.booking_status == BookingStatusEnum.CONFIRMED:
                    expected_booked += b.rooms_count

        if room_type_id not in nights_by_room_type:
            nights_by_room_type[room_type_id] = {
                n.date: n for n in stay_inventory.list_nights(db, room_type_id)
            }
        row = nights_by_room_type[room_type_id].get(night)
        checks.append(RowCheck(
            room_type_id=room_type_id,
            night=night,
            actual_reserved=row.reserved_count if row else 0,
            actual_booked=row.book_count if row else 0,
            expected_reserved=expected_reserved,
            expected_booked=expected_booked,
            old_rooms=rooms,
            missing_row=row is None,
        ))
    return checks


def apply_fixes(db: Session, checks: list[RowCheck]) -> int:
    """Release the extra count on each fixable row. Does not commit.

    Returns the number of rows fixed.
    """
    fixed = 0
    for c in checks:
        if c.verdict != "fixable":
            continue
        one_night = Stay(c.night, c.night + timedelta(days=1))
        if c.extra_reserved:
            stay_inventory.release_hold(db, c.room_type_id, one_night, c.extra_reserved)
        if c.extra_booked:
            stay_inventory.release_booked(db, c.room_type_id, one_night, c.extra_booked)
        fixed += 1
    return fixed


def _print_report(checks: list[RowCheck]) -> None:
    print(f"{'room type':>9}  {'date':<10}  {'reserved':>15}  {'booked':>15}  {'old rooms':>9}  verdict")
    print(f"{'':>9}  {'':<10}  {'actual/expect':>15}  {'actual/expect':>15}")
    for c in checks:
        print(f"{c.room_type_id:>9}  {c.night.isoformat():<10}  "
              f"{f'{c.actual_reserved}/{c.expected_reserved}':>15}  "
              f"{f'{c.actual_booked}/{c.expected_booked}':>15}  "
              f"{c.old_rooms:>9}  {c.verdict}{' (no row)' if c.missing_row else ''}")
    totals = defaultdict(int)
    for c in checks:
        totals[c.verdict] += 1
    print(f"\nrows: {len(checks)}  ok: {totals['ok']}  "
          f"fixable: {totals['fixable']}  mismatch: {totals['mismatch']}")


def use_one_snapshot(db: Session) -> None:
    """Make every read in the session's next transaction use one snapshot.

    Call it before the first query of the transaction. On Postgres it sets
    REPEATABLE READ. A row lock on a row that another transaction changed
    after the snapshot then raises a serialization error, so the script can
    never act on counts that it did not read. SQLite runs every transaction
    as SERIALIZABLE already, so the function does nothing there.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})


def is_serialization_failure(exc: DBAPIError) -> bool:
    return getattr(exc.orig, "pgcode", None) == "40001"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--created-before", required=True, type=datetime.fromisoformat,
                        help="ISO time. Bookings created before it are old bookings. "
                             "A time without a zone is UTC.")
    parser.add_argument("--apply", action="store_true",
                        help="Fix the fixable rows and commit. Without it, nothing changes.")
    args = parser.parse_args(argv)

    from app.database import SessionLocal

    with SessionLocal() as db:
        use_one_snapshot(db)
        checks = check_rows(db, args.created_before)
        _print_report(checks)
        if not args.apply:
            db.rollback()
            print("\nDry run. Nothing changed. Add --apply to fix the fixable rows.")
            return 0
        try:
            fixed = apply_fixes(db, checks)
            db.commit()
        except DBAPIError as exc:
            db.rollback()
            if not is_serialization_failure(exc):
                raise
            print("\nA booking changed a checked row during the run. "
                  "Nothing changed. Run the script again.")
            return 1
        print(f"\nFixed {fixed} rows and committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
