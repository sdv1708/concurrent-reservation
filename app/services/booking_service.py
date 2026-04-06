from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
import stripe
from app.models.booking import Booking
from app.models.inventory import Inventory
from app.models.guest import Guest
from app.models.user import User
from app.models.enums import BookingStatusEnum
from app.schemas.booking import BookingRequest
from app.pricing.pricing_service import calculate_total_price
from app.database import get_by_id, create_record
from app.config import settings


def has_booking_expired(booking: Booking) -> bool:
    """
    REFERENCE — A booking expires 10 minutes after creation if payment has not started.

    This guard is called in add_guests and initiate_payment (but NOT in cancel_booking —
    a confirmed booking's cancellation window is different).

    Notice the timezone handling: `created_at` from the DB may be naive (no timezone info).
    We attach UTC explicitly before comparing to datetime.now(timezone.utc).
    """
    
    created = booking.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > created + timedelta(minutes=10)


def init_booking(db: Session, data: BookingRequest, current_user: User) -> Booking:
    """
    REFERENCE — The most important function in the app. Study this before implementing below.

    The core problem this solves: two guests clicking "Book" at the exact same time for
    the last available room. Without a lock, both would see availability and both might succeed.

    The solution — SELECT FOR UPDATE (pessimistic locking):
      - The query fetches inventory rows matching: room, dates, available count
      - .with_for_update() locks those rows at the database level
      - No other transaction can read or write those rows until this one commits
      - If len(rows) != days, the room isn't available and we raise 400

    After locking: reserved_count is incremented (temporary hold for 10-min payment window).
    Price is computed using the pricing chain (dynamic pricing across all dates).
    The booking is created with status=RESERVED.
    """
    from app.models.hotel import Hotel
    from app.models.room import Room

    hotel = get_by_id(db, Hotel, data.hotel_id)
    if not hotel:
        raise HTTPException(404, f"Hotel not found: {data.hotel_id}")

    room = get_by_id(db, Room, data.room_id)
    if not room:
        raise HTTPException(404, f"Room not found: {data.room_id}")

    days = (data.check_out_date - data.check_in_date).days + 1

    # Lock matching inventory rows — no other transaction can read/write these until we commit
    inventory_rows = db.execute(
        select(Inventory)
        .where(
            Inventory.room_id == data.room_id,
            Inventory.date.between(data.check_in_date, data.check_out_date),
            Inventory.closed == False,
            (Inventory.total_count - Inventory.book_count - Inventory.reserved_count) >= data.rooms_count,
        )
        .with_for_update()   # ← pessimistic lock
    ).scalars().all()

    if len(inventory_rows) != days:
        raise HTTPException(400, "Room not available for the selected dates")

    # Hold the rooms (temporary reservation — 10 min window)
    for inv in inventory_rows:
        inv.reserved_count += data.rooms_count

    # Calculate price: per-room total × number of rooms
    price_per_room = calculate_total_price(inventory_rows)
    total_price = price_per_room * data.rooms_count

    booking = create_record(
        db, Booking,
        hotel_id=data.hotel_id,
        room_id=data.room_id,
        user_id=current_user.id,
        rooms_count=data.rooms_count,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        booking_status=BookingStatusEnum.RESERVED,
        amount=total_price,
    )
    db.commit()
    return booking


def add_guests(db: Session, booking_id: int, guest_ids: list[int], current_user: User) -> Booking:
    """
    Attach a list of saved guests to a booking, advancing its status to GUESTS_ADDED.

    State machine rules (check these IN ORDER — order matters):
      1. Does the booking exist? → 404 if not
      2. Does it belong to this user? → 403 if not
      3. Has the 10-minute window expired? → 400 "Booking has expired"
         Use the has_booking_expired() helper already defined above.
      4. Is the booking in RESERVED status? → 400 if in any other state
         (Guests can only be added to a fresh, unconfirmed booking)

    After all checks pass:
      - Fetch each Guest by ID from the guest_ids list (list comprehension works well here)
      - Set booking.guests = [that list of guest objects]
        (This updates the many-to-many join table automatically)
      - Advance status to GUESTS_ADDED
      - Commit, then call db.refresh(booking) so the guests relationship is populated
      - Return the booking

    Think about: what is db.refresh() doing, and why is it needed AFTER the commit?
    """
    booking = get_by_id(db, Booking, booking_id)
    if not booking:
        raise HTTPException(404, f"Booking not found: {booking_id}")
    if booking.user_id != current_user.id:
        raise HTTPException(403, "You do not own this booking")
    if has_booking_expired(booking):
        raise HTTPException(400, "Booking has expired")
    if booking.booking_status != BookingStatusEnum.RESERVED:
        raise HTTPException(400, f"Cannot add guests to a booking with status: {booking.booking_status}")

    guests = [get_by_id(db, Guest, gid) for gid in guest_ids]
    booking.guests = guests
    booking.booking_status = BookingStatusEnum.GUESTS_ADDED
    db.commit()
    db.refresh(booking)
    return booking


def initiate_payment(db: Session, booking_id: int, current_user: User):
    """
    Create a Stripe Checkout session and advance the booking to PAYMENTS_PENDING.

    State machine rules (check in order):
      1. Booking exists? → 404
      2. Owned by this user? → 403
      3. Booking expired? → 400
      4. Status must be RESERVED or GUESTS_ADDED → 400 for anything else
         (Guests are optional — payment can start before adding guests)

    The Stripe call:
      - Use stripe.checkout.Session.create(...)
      - Payment method: "card"
      - Amount: booking.amount converted to cents (Stripe uses integer cents, not decimals)
      - Mode: "payment" (one-time, not subscription)
      - success_url and cancel_url both point to the payment status page
        Use settings.frontend_url as the base (already imported above)

    After the Stripe call:
      - Store session.id in booking.payment_session_id
        (This is how the webhook will find the booking later)
      - Set status to PAYMENTS_PENDING
      - Commit
      - Return session.url (the URL the user should be redirected to for payment)

    The response_model in the router is BookingPaymentInitResponse — what field does it have?
    """
    booking = get_by_id(db, Booking, booking_id)
    if not booking:
        raise HTTPException(404, f"Booking not found: {booking_id}")
    if booking.user_id != current_user.id:
        raise HTTPException(403, "You do not own this booking")
    if has_booking_expired(booking):
        raise HTTPException(400, "Booking has expired")
    if booking.booking_status not in (BookingStatusEnum.RESERVED, BookingStatusEnum.GUESTS_ADDED):
        raise HTTPException(400, f"Cannot initiate payment for booking with status: {booking.booking_status}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": int(booking.amount * 100),  # Stripe uses cents
                "product_data": {"name": f"Booking #{booking.id}"},
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{settings.frontend_url}/bookings/{booking.id}/status",
        cancel_url=f"{settings.frontend_url}/bookings/{booking.id}/status",
    )

    booking.payment_session_id = session.id
    booking.booking_status = BookingStatusEnum.PAYMENTS_PENDING
    db.commit()
    return session.url


def cancel_booking(db: Session, booking_id: int, current_user: User) -> Booking:
    """
    Cancel a confirmed booking and issue a Stripe refund.

    State machine rules:
      1. Booking exists? → 404
      2. Owned by this user? → 403
      3. Status must be CONFIRMED → 400 if anything else
         (Only confirmed bookings can be cancelled — you can't cancel a RESERVED or PENDING one)
         Notice: no expiry check here — why not?

    The inventory rollback (use SELECT FOR UPDATE — same reason as booking init):
      - Lock inventory rows for this booking's room and date range
      - For each row: book_count -= booking.rooms_count
        (Use max(0, ...) to prevent negative values from any edge case)

    The Stripe refund:
      - Retrieve the original session: stripe.checkout.Session.retrieve(booking.payment_session_id)
      - Create a refund against the payment intent: stripe.Refund.create(payment_intent=session.payment_intent)

    After both operations:
      - Set status to CANCELLED
      - Commit

    What should you return? Look at the router's response_model.
    """
    booking = get_by_id(db, Booking, booking_id)
    if not booking:
        raise HTTPException(404, f"Booking not found: {booking_id}")
    if booking.user_id != current_user.id:
        raise HTTPException(403, "You do not own this booking")
    if booking.booking_status != BookingStatusEnum.CONFIRMED:
        raise HTTPException(400, f"Only confirmed bookings can be cancelled, current status: {booking.booking_status}")

    # Release inventory using SELECT FOR UPDATE — same reason as booking init
    inventory_rows = db.execute(
        select(Inventory)
        .where(
            Inventory.room_id == booking.room_id,
            Inventory.date.between(booking.check_in_date, booking.check_out_date),
        )
        .with_for_update()
    ).scalars().all()

    for inv in inventory_rows:
        inv.book_count = max(0, inv.book_count - booking.rooms_count)

    # Stripe refund against the original payment intent
    stripe_session = stripe.checkout.Session.retrieve(booking.payment_session_id)
    stripe.Refund.create(payment_intent=stripe_session.payment_intent)

    booking.booking_status = BookingStatusEnum.CANCELLED
    db.commit()
    return booking


def confirm_booking(db: Session, session_id: str) -> None:
    """
    Called by the Stripe webhook after a successful payment. Finalizes the booking.

    This is Phase 12 — triggered externally by Stripe, not by the user directly.

    Steps:
      1. Find the booking using payment_session_id (NOT a primary key lookup —
         use db.query(Booking).filter(...).first())
         If not found → 404

      2. SELECT FOR UPDATE on inventory rows (same date range + room_id as the booking)
         Why is the lock needed here?
         (Two webhooks for the same session could theoretically arrive close together)

      3. For each inventory row:
           - reserved_count decreases by booking.rooms_count (the hold is released)
           - book_count increases by booking.rooms_count (now fully confirmed)
           Use max(0, ...) on the decrement to be safe

      4. Set booking.booking_status = CONFIRMED
      5. Commit

    The status flow for a room slot:
      RESERVED → reserved_count++ (held)
      CONFIRMED → reserved_count-- AND book_count++ (converted from hold to confirmed)
      CANCELLED → book_count-- (released back to available)
    """
    booking = db.query(Booking).filter(Booking.payment_session_id == session_id).first()
    if not booking:
        raise HTTPException(404, f"Booking not found for session: {session_id}")

    # Lock inventory rows — prevents concurrent webhook deliveries from double-confirming
    inventory_rows = db.execute(
        select(Inventory)
        .where(
            Inventory.room_id == booking.room_id,
            Inventory.date.between(booking.check_in_date, booking.check_out_date),
        )
        .with_for_update()
    ).scalars().all()

    for inv in inventory_rows:
        inv.reserved_count = max(0, inv.reserved_count - booking.rooms_count)
        inv.book_count += booking.rooms_count

    booking.booking_status = BookingStatusEnum.CONFIRMED
    db.commit()
