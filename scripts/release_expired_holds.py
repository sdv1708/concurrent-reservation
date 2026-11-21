"""Release every hold whose 10-minute payment window ran out.

The periodic job for expired holds. Each run makes one pass and exits.
Run it every minute from cron, Windows Task Scheduler, or a platform
scheduler. Two runs at the same time are safe: each booking is locked
before its release, and a second release of a booking changes nothing.

init_booking also releases expired holds that block a new hold, so a
stopped job does not block holds. The job keeps search results correct,
because search reads the counts and releases nothing.

Usage (from the repository root):
  python -m scripts.release_expired_holds
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from app.database import SessionLocal
    from app.services.booking_service import release_expired_holds

    with SessionLocal() as db:
        released = release_expired_holds(db)
    print(f"Released {released} expired holds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
