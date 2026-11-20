# Concurrent Reservation API

A hotel booking API built with FastAPI, SQLAlchemy 2.0, and Postgres. Hotel managers list room types. Guests place a hold on rooms for a stay, pay through Stripe Checkout, and the Stripe webhook turns the hold into booked rooms.

The main problem this project solves is concurrency: two guests must never both get the last available room for the same night. This README explains how the code solves it, what the tests prove, and what the code does not do yet.

This is a portfolio project. It is not deployed to production.

## Contents

- [Domain terms](#domain-terms)
- [Architecture](#architecture)
- [The Stay Inventory module](#the-stay-inventory-module)
- [Concurrency design](#concurrency-design)
- [Booking lifecycle](#booking-lifecycle)
- [Pricing](#pricing)
- [Authentication and roles](#authentication-and-roles)
- [API routes](#api-routes)
- [Tests](#tests)
- [Local setup](#local-setup)
- [Deploying the Stay Inventory change](#deploying-the-stay-inventory-change)
- [Deploying the release of expired holds](#deploying-the-release-of-expired-holds)
- [Known limitations](#known-limitations)
- [Design questions and answers](#design-questions-and-answers)

## Domain terms

[CONTEXT.md](CONTEXT.md) defines the terms. The code, tests, and commits use them with these meanings:

| Term | Meaning |
| --- | --- |
| Room type | A kind of room in one hotel, with a number of identical rooms. The code calls it `Room`. |
| Stay | The nights from the check-in date up to, but not including, the check-out date. 2026-08-05 to 2026-08-07 is 2 nights. |
| Night | One calendar date on which a guest occupies a room. The check-out date is never a night. |
| Hold | A claim on rooms for a stay, placed before payment. Stored in `reserved_count`. |
| Booked | Rooms that a guest paid for. Stored in `book_count`. |
| Available | `total_count - book_count - reserved_count` on a night that is not closed. |
| Closed | A night on which the manager stops new holds. Existing holds and booked rooms stay valid. |

## Architecture

```
app/routers/      HTTP layer: parse input, inject the session and the user, call one service
app/services/     Business rules and ownership checks (404 and 403)
  stay_inventory.py   The only code that reads availability or changes Inventory counts
app/pricing/      Price decorator chain, applied to the nights of a hold
app/models/       SQLAlchemy models
app/schemas/      Pydantic request and response models
alembic/          Schema migrations
scripts/          One-off operations scripts
```

The services raise FastAPI `HTTPException`, so most of the service layer depends on FastAPI. `stay_inventory.py` is the exception. It imports nothing from `fastapi` and raises domain errors. `app/main.py` maps `StayUnavailableError` to 409 Conflict.

## The Stay Inventory module

The `Inventory` table has one row for each room type and night. [stay_inventory.py](app/services/stay_inventory.py) owns every rule about these rows. Before this module existed, five call sites each had their own copy of the availability formula, the stay-to-dates rule, and the lock. Two of those copies disagreed: booking held `nights + 1` rows, and search counted `nights` rows.

| Operation | Effect |
| --- | --- |
| `place_hold(db, room_type_id, stay, rooms)` | Locks the stay's rows. Checks that each night exists, is not closed, and has enough available rooms. Increments `reserved_count`. Returns a read-only copy of each held night for pricing. |
| `book_hold(...)` | Moves `rooms` from `reserved_count` to `book_count` on each night. |
| `release_hold(...)` | Decrements `reserved_count`. |
| `release_booked(...)` | Decrements `book_count`. |
| `ensure_rows(db, room_type_id)` | Makes sure that a row exists for each of the 365 nights from today. Running it again adds nothing. |
| `change_nights(db, room_type_id, first, last, closed=, surge_factor=)` | Admin change over an inclusive date range. |
| `list_nights(db, room_type_id)` | All rows of a room type, in date order. |
| `available_hotels(city, stay, rooms)` | Subquery for hotel search: hotels in the city where at least one room type covers every night of the stay. |

These rules apply to every operation:

- **The module never commits.** It adds and flushes. The caller commits once, so that, for example, the hold and the new `Booking` commit in one transaction.
- **A count never goes below zero.** If a change would make a count negative, the module raises `InventoryCountError`. That condition is a bug in the caller, so the module does not clamp the value.
- **The module does no authorization.** The caller checks ownership first.
- **The module does not know about bookings.** It takes a room type id, a `Stay`, and a room count, and it never imports `Booking`.

## Concurrency design

### Pessimistic row locks, in a fixed order

Each operation that changes counts runs this query first:

```sql
SELECT ... FROM "Inventory"
WHERE room_id = :room_type AND date >= :check_in AND date < :check_out
ORDER BY date
FOR UPDATE
```

- **Check after the lock.** The query locks every row of the stay and then checks availability in Python. Concurrent transactions wait on the lock. When one gets the lock, Postgres gives it the newest committed version of each row. So two guests cannot both see "1 available" and both take the room.
- **Lock all rows, not only the matching ones.** The old query put the availability condition in the `WHERE` clause, so it locked only the rows that matched. The new query locks the whole stay, so the set of locked rows does not depend on the counts.
- **Fixed order.** Two overlapping stays lock their shared nights in date order. Thus neither transaction can hold a later night while it waits for an earlier one, and that removes the deadlock between two holds.
- **Isolation level.** The default Postgres level, READ COMMITTED, is enough together with the row locks. The code does not need SERIALIZABLE, and it does not need a retry loop.

### Idempotent row generation

`ensure_rows` reads the nights that already exist and inserts only the missing ones, with `INSERT ... ON CONFLICT (hotel_id, room_id, date) DO NOTHING`. If two runs for the same room type overlap, the `unique_hotel_room_date` constraint decides which insert wins, and the other insert skips the row without an error. Room creation on an active hotel calls `ensure_rows`. Activation also calls it, through `PATCH /activate` or through a `PUT` that sets `active` to true.

### Idempotent payment webhook

Stripe can deliver `checkout.session.completed` more than once. `confirm_booking` locks the `Booking` row with `FOR UPDATE`. If the status is already `CONFIRMED`, it returns without a change. The row lock makes this check safe when two deliveries arrive at the same time: the second delivery waits, then reads `CONFIRMED`.

### Release of expired holds

A hold has a payment window of 10 minutes from `init`. After that, `expire_hold` in [booking_service.py](app/services/booking_service.py) can release it. It runs in this order:

1. Lock the `Booking` row with `FOR UPDATE`.
2. Check that the status is `RESERVED`, `GUESTS_ADDED`, or `PAYMENTS_PENDING`, and that the window ran out. If not, change nothing.
3. Call `release_hold` and set the status to `EXPIRED`.
4. Commit.

Two triggers call `expire_hold`:

- **The periodic job.** [scripts/release_expired_holds.py](scripts/release_expired_holds.py) releases every expired hold, then exits. Run it every minute from cron or another scheduler. It keeps search results correct.
- **The lazy release.** Before `init_booking` places a hold, it releases the expired holds of the same room type that share a night with the new stay. Thus a stopped job never makes a stay look unavailable to a new hold.

Every function that changes a booking's status locks the `Booking` row before it reads the status: `expire_hold`, `confirm_booking`, `add_guests`, and `initiate_payment`. So a release and a webhook on one booking run one after the other:

| First to get the lock | Second one sees | Result |
| --- | --- | --- |
| The webhook | `CONFIRMED` | The webhook books the hold, which still exists. The release changes nothing. |
| The release | `EXPIRED` | The webhook places a new hold for the same stay and books it. If the stay is unavailable or a night is closed, the webhook refunds the payment and sets `CANCELLED`. |

Each release is its own transaction. It locks one `Booking` row and then the rows of one stay, in date order. The job and the lazy release thus never hold the rows of two stays at once, so they keep the deadlock rule above.

### What the tests prove about concurrency

SQLite does not support `FOR UPDATE`, and SQLAlchemy leaves it out of the SQL on SQLite. So the SQLite test suite proves the counting rules, not the locking. Three opt-in tests run against a real Postgres:

- [test_stay_inventory_postgres.py](tests/test_stay_inventory_postgres.py): two threads with separate sessions try to hold the last room for the same stay. The test checks that exactly one succeeds.
- [test_stay_inventory_postgres.py](tests/test_stay_inventory_postgres.py): a booking confirms while the data fix script runs. The test checks that the script changes nothing and that a second run fixes only the old extra count.
- [test_expired_holds_postgres.py](tests/test_expired_holds_postgres.py): one thread releases an expired hold, and another thread confirms the same booking. The test checks that the booking always ends `CONFIRMED`, with `book_count` 1 and `reserved_count` 0.

The tests are skipped when `TEST_DATABASE_URL` is not set. See [Tests](#tests).

## Booking lifecycle

```mermaid
stateDiagram-v2
    [*] --> RESERVED: POST /bookings/init (place_hold)
    RESERVED --> GUESTS_ADDED: POST /bookings/{id}/addGuests
    RESERVED --> PAYMENTS_PENDING: POST /bookings/{id}/payments
    GUESTS_ADDED --> PAYMENTS_PENDING: POST /bookings/{id}/payments
    PAYMENTS_PENDING --> CONFIRMED: Stripe webhook (book_hold)
    RESERVED --> EXPIRED: window ran out (release_hold)
    GUESTS_ADDED --> EXPIRED: window ran out (release_hold)
    PAYMENTS_PENDING --> EXPIRED: window ran out (release_hold)
    EXPIRED --> CONFIRMED: Stripe webhook, stay available (place_hold + book_hold)
    EXPIRED --> CANCELLED: Stripe webhook, stay unavailable (refund)
    CONFIRMED --> CANCELLED: POST /bookings/{id}/cancel (release_booked + refund)
```

- `init` checks that the hotel is active and that the room type belongs to the hotel. It releases the expired holds that block the stay, places the hold, prices the held nights, and stores the total in `Booking.amount`.
- `addGuests` and `payments` work only within 10 minutes of `init`. After that, they return 400.
- After 10 minutes, the periodic job or the next `init` on the same nights releases the hold and sets `EXPIRED`. See [Release of expired holds](#release-of-expired-holds).
- The webhook verifies the Stripe signature against the raw request body before it reads the event.
- The guest can pay after the hold expired, because the Stripe Checkout session lives longer than 10 minutes. The webhook then holds the stay again at the paid amount. If the stay is unavailable, the webhook refunds the payment.
- `cancel` works only on a `CONFIRMED` booking. It releases the booked rooms and creates a Stripe refund.

## Pricing

[app/pricing/](app/pricing/) is a decorator chain. Each layer wraps the previous layer and changes its result. The chain is built in this order:

| Layer | Rule |
| --- | --- |
| Base | The night's `price`, which is the room type's `base_price` copied when the row was made |
| Surge | Multiplied by `surge_factor` when it is above 1 |
| Occupancy | +20% when more than 80% of the rooms are booked |
| Urgency | +15% when the night is 0 to 7 days from today |
| Holiday | +25% on Saturday and Sunday (despite the name, it checks for weekends only) |

The booking total is the sum of the chain over the held nights, multiplied by `rooms_count`. Hotel search shows the raw minimum `price`, not the dynamic price, so the search price and the booking total can differ.

## Authentication and roles

- **Access token:** a JWT that lives 10 minutes. The client sends it in the `Authorization: Bearer` header.
- **Refresh token:** a JWT that lives 180 days, in an `HttpOnly`, `SameSite=Lax` cookie. `POST /auth/refresh` returns a new access token.
  - `HttpOnly` stops JavaScript from reading the cookie. The cookie does not have the `Secure` flag.
  - The tokens are stateless, so the server cannot revoke one before it expires.
- **Roles:** signup gives a user the `GUEST` role. The `/admin/*` routes need `HOTEL_MANAGER`. No route grants that role, so you add it in the `user_roles` table. `ADMIN` is defined in the enum but no route uses it.
- **Ownership:** each service checks that the user owns the hotel, room type, booking, or guest. It returns 404 when the record does not exist and 403 when another user owns it.

## API routes

Swagger UI is at `/swagger-ui.html`. Every route except signup, login, refresh, and the webhook needs an access token.

| Area | Routes |
| --- | --- |
| Auth | `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh` |
| Users | `GET/PATCH /users/profile`, `GET /users/myBookings`, `GET/POST /users/guests`, `PUT/DELETE /users/guests/{id}` |
| Browse | `GET /hotels/search` (JSON body: `city`, `start_date`, `end_date`, `rooms_count`, `page` from 1, `size`), `GET /hotels/{id}/info` |
| Bookings | `POST /bookings/init`, `POST /bookings/{id}/addGuests`, `POST /bookings/{id}/payments`, `POST /bookings/{id}/cancel`, `GET /bookings/{id}/status` |
| Hotel admin | `POST/GET /admin/hotels`, `GET/PUT/DELETE /admin/hotels/{id}`, `PATCH /admin/hotels/{id}/activate`, `GET /admin/hotels/{id}/bookings`, `GET /admin/hotels/{id}/reports` |
| Room type admin | `POST/GET /admin/hotels/{hotel_id}/rooms`, `GET/PUT/DELETE /admin/hotels/{hotel_id}/rooms/{id}` |
| Inventory admin | `GET /admin/inventory/rooms/{room_id}`, `PATCH /admin/inventory/rooms/{room_id}` (close nights, set surge) |
| Webhook | `POST /webhook/payment` (Stripe) |

The error codes are:
- 404 and 403 for records that do not exist or that another user owns.
- 409 when a stay is unavailable or an email is already registered.
- 400 for a booking in the wrong state or past its payment window.
- 422 for invalid input.

## Tests

```powershell
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

The suite has 61 tests. 58 run on SQLite (`./test.db`), and the 3 Postgres tests are skipped without a Postgres URL:

| File | Covers |
| --- | --- |
| `test_stay_inventory.py` | The module, called directly: the stay rule, holds, booked rooms, releases, below-zero errors, closed nights, row generation, activation, and search grouped by room type and filtered by city |
| `test_phase11_bookings.py` | HTTP booking flow: 409 for an unavailable stay, a repeated webhook, input validation, guest ownership |
| `test_expired_holds.py` | Release of expired holds: the release, a second release that changes nothing, the lazy release in `init`, both orders of the race with the webhook, and the refund when the stay is taken or closed |
| `test_phase6_hotels.py`, `test_phase8_inventory.py`, `test_phase5_users.py` | Hotel admin, search route, inventory admin, users and guests |
| `test_fix_check_out_night_counts.py` | The one-off data fix script |
| `test_stay_inventory_postgres.py` | Concurrent holds, and a booking that changes during the data fix, on a real Postgres. Opt-in. |
| `test_expired_holds_postgres.py` | A release and a webhook on the same booking at the same time, on a real Postgres. Opt-in. |

To run the Postgres tests, point `TEST_DATABASE_URL` at a database that the tests can write to. The tests create the tables if needed and delete their own rows:

```powershell
$env:TEST_DATABASE_URL = "postgresql://user:password@localhost:5432/reservation_test"
python -m pytest -q -m postgres
```

Know these limits of the test setup:
- **Shared test database.** Services commit, so data from HTTP tests stays in `test.db` until the session ends. Tests use unique names and cities so that they do not depend on each other.
- **Mocked Stripe.** Stripe calls are mocked. No test talks to Stripe.

## Local setup

1. Install Python 3.11. The Dockerfile uses 3.11, and the tests also pass on 3.13.
2. Create a virtual environment and install the dependencies:
   ```powershell
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
   ```
3. Copy `.env.example` to `.env` and set `DATABASE_URL` (Postgres), `JWT_SECRET_KEY`, and the Stripe test keys. The app always connects to Postgres. Only the tests use SQLite.
4. Create the schema:
   ```powershell
   venv\Scripts\alembic upgrade head
   ```
5. Start the server:
   ```powershell
   venv\Scripts\uvicorn app.main:app --reload
   ```
6. Run the release job every minute, from cron or Windows Task Scheduler. One run makes one pass and exits:
   ```powershell
   venv\Scripts\python -m scripts.release_expired_holds
   ```

`bcrypt` is pinned to 4.0.1, because `passlib` 1.7.4 fails with later versions.

## Deploying the Stay Inventory change

Before this change, each booking held one extra row: the row on its check-out date. The new code releases only the nights of a stay, so it would never release that extra count. [scripts/fix_check_out_night_counts.py](scripts/fix_check_out_night_counts.py) removes it. Run it once at deploy time:

1. Stop the old app version.
2. Deploy the new version.
3. Run the script without `--apply`. This is a dry run that only prints a report. For `--created-before`, use the time the old version stopped.
4. Read the report, then run the script again with `--apply`.

```powershell
venv\Scripts\python -m scripts.fix_check_out_night_counts --created-before 2026-11-20T09:00:00+00:00
```

The script compares each check-out row with the counts that the bookings call for under the new rule. It changes a row only when the extra count matches the old bookings exactly. It reports every other difference and does not change it. A second run changes nothing.

The new version can keep serving traffic while the script runs. On Postgres, the script reads every row from one REPEATABLE READ snapshot. If a booking changes a row that the script then tries to fix, Postgres raises a serialization error. The script then rolls back every change and exits with code 1, and you run it again.

## Deploying the release of expired holds

The new code writes the booking status `EXPIRED`. The initial migration made the status a native Postgres enum type, so the database needs the new value first:

1. Run `venv\Scripts\alembic upgrade head` before the new version starts. The migration adds `EXPIRED` to the `bookingstatusenum` type.
2. Deploy the new version.
3. Schedule `python -m scripts.release_expired_holds` every minute.

The first job run releases every hold that expired before the deploy. If the check-out fix above did not run yet, it still works afterward: it expects the old extra count on the check-out date of an `EXPIRED` booking.

## Known limitations

These are open on purpose. Each one is a separate piece of work.

- **The release job needs an outside scheduler.** Nothing in the app runs `scripts/release_expired_holds.py`. If no scheduler runs it, `init` still releases the expired holds that block a new hold. But search keeps hiding rooms behind expired holds until the next job run.
- **A late payment can be refunded twice in rare cases.** When the webhook refunds a payment for an expired hold, it calls Stripe before it commits, as `cancel_booking` does. If the commit fails, Stripe retries the webhook. The Stripe idempotency key stops a second refund for 24 hours only. A retry after that can try to refund again, and Stripe rejects it, so the webhook fails until Stripe stops its retries.
- **A late payment books at the price of the old hold.** The webhook holds the stay again at `Booking.amount`, even if the nights now cost more. The webhook also re-holds stays whose nights are in the past.
- **`cancel_booking` does not lock the `Booking` row.** Two concurrent cancels of one booking can both pass the status check. The second cancel then releases the booked rooms a second time. Only Stripe stops it: Stripe rejects a second full refund, and that error rolls back the second release. The other status changes lock the row first, so `cancel_booking` is the one exception.
- **The 365-night window does not move.** `ensure_rows` runs only at room creation and activation. No daily job adds the next night.
- **Changes to a room type or hotel do not reach existing rows.** Changing `base_price`, `total_count`, or the hotel's `city` changes only rows made later. A city change thus hides the hotel's old rows from search in the new city.
- **The refund happens before the commit.** `cancel_booking` calls Stripe while it holds the row locks and before it commits. If the commit fails after the refund, the guest gets the money back but the booking stays `CONFIRMED`.
- **Search uses GET with a JSON body.** Some HTTP clients and proxies drop a GET body.
- **Search shows the raw price.** The search price is the raw `price`, and the booking total is the dynamic price.
- **Auth gaps.** There is no token revocation, the refresh cookie has no `Secure` flag, and no route grants `HOTEL_MANAGER`.
- **Most services depend on FastAPI.** They raise `HTTPException`. Only `stay_inventory.py` is free of FastAPI.
- **The Postgres tests were not run.** They need a Postgres database, and no Postgres server was available when they were written. This applies to all 3 tests, including `test_expired_holds_postgres.py`.

## Design questions and answers

**Why pessimistic locking and not optimistic locking with a version column?**
The contention is on a small set of rows: the last rooms on popular nights. With optimistic locking, the transaction that loses must retry, and under load most attempts on a hot night lose. With pessimistic locking, the second transaction waits a few milliseconds and then gets a definite answer. The cost is that locks are held for the length of the transaction, so the transaction must stay short. One example: `init_booking` does no network call while it holds the locks.

**Why counts per night, and not one row per physical room?**
A guest asks for "2 rooms of this type", not for room 204. With counts, a hold for one night is one row update, and availability is one formula. With a row for each physical room, a hold must choose and lock specific rooms, and search must count them.

**How do you prevent deadlocks?**
Every operation locks the rows of one room type in date order. Two transactions that need the same nights request them in the same order, so they cannot each hold a row that the other needs.

**What happens if the webhook arrives twice?**
The second delivery locks the `Booking` row, sees `CONFIRMED`, and returns. A test sends the same event twice and checks that `book_count` went up once.

**What happens if the guest pays after the hold expired?**
The Stripe Checkout session lives longer than the 10-minute window, so this can happen. If the hold still exists, the webhook books it. If the hold was released, the booking is `EXPIRED`. The webhook then places a new hold for the same stay and books it, because the guest already paid. If the stay is now unavailable, the webhook refunds the payment and sets `CANCELLED`. The release and the webhook both lock the `Booking` row first, so only one of them acts on the booking at a time.

**Why release in two places?**
The lazy release in `init` makes sure that an expired hold never blocks a new hold, even if the job stops. It does not help search, which only reads the counts. The periodic job keeps the counts, and thus search, correct.

**Why does the module never commit?**
The caller owns the unit of work. `init_booking` must commit the hold and the `Booking` together. If it committed the hold first and then failed, it would leave a hold that no booking owns.

**Why raise an error on a negative count, and not clamp to zero?**
A negative count means the caller released something it never held. A clamp hides that bug and corrupts availability. An error rolls back the transaction and shows the bug.

**Why is `city` stored on Inventory rows?**
Search filters by city and date in one table, without a join to `Hotel`. The cost is that a city change does not reach existing rows. See [Known limitations](#known-limitations).

**How was the code built?**
I built it with AI-assisted tooling under my direction. I set the design decisions in advance: the locking strategy, the module boundary, the stay rule, the transaction ownership, and the error mapping. The tests check each step. The git history shows each change as a small commit.
