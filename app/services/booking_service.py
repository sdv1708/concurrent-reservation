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
    REFERENCE — Booking expires 10 minutes after creation if payment not started.
    Check this before addGuests and initiatePayment (NOT before cancel).
    """
    created = booking.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > created + timedelta(minutes=10)


def init_booking(db: Session, data: BookingRequest, current_user: User) -> Booking:
    """
    REFERENCE — The most important service method in the app.
    Uses SELECT FOR UPDATE to prevent concurrent double-bookings.
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
    # TODO:
    #   booking = get_by_id(db, Booking, booking_id) → 404 if not found
    #   if booking.user_id != current_user.id → raise 403
    #   if has_booking_expired(booking) → raise 400 "Booking has expired"
    #   if booking.booking_status != RESERVED → raise 400 "Invalid state"
    #   guests = [get_by_id(db, Guest, gid) for gid in guest_ids]
    #   booking.guests = guests
    #   booking.booking_status = GUESTS_ADDED
    #   db.commit()
    #   return booking
    pass


def initiate_payment(db: Session, booking_id: int, current_user: User):
    # TODO:
    #   booking = get_by_id(db, Booking, booking_id) → 404 if not found
    #   if booking.user_id != current_user.id → raise 403
    #   if has_booking_expired(booking) → raise 400
    #   if booking.booking_status not in (RESERVED, GUESTS_ADDED) → raise 400
    #
    #   session = stripe.checkout.Session.create(
    #       payment_method_types=["card"],
    #       line_items=[{
    #           "price_data": {
    #               "currency": "usd",
    #               "product_data": {"name": f"Hotel Booking #{booking.id}"},
    #               "unit_amount": int(booking.amount * 100),  # Stripe uses cents
    #           },
    #           "quantity": 1,
    #       }],
    #       mode="payment",
    #       success_url=f"{settings.frontend_url}/payments/{booking.id}/status",
    #       cancel_url=f"{settings.frontend_url}/payments/{booking.id}/status",
    #   )
    #
    #   booking.payment_session_id = session.id
    #   booking.booking_status = PAYMENTS_PENDING
    #   db.commit()
    #   return session.url
    pass


def cancel_booking(db: Session, booking_id: int, current_user: User) -> Booking:
    # TODO:
    #   booking = get_by_id(db, Booking, booking_id) → 404 if not found
    #   if booking.user_id != current_user.id → raise 403
    #   if booking.booking_status != CONFIRMED → raise 400
    #
    #   SELECT FOR UPDATE inventory rows (same date range + room_id)
    #   For each: book_count = max(0, book_count - booking.rooms_count)
    #
    #   Refund via Stripe:
    #   session = stripe.checkout.Session.retrieve(booking.payment_session_id)
    #   stripe.Refund.create(payment_intent=session.payment_intent)
    #
    #   booking.booking_status = CANCELLED
    #   db.commit()
    pass


def confirm_booking(db: Session, session_id: str) -> None:
    """Called by the Stripe webhook after successful payment."""
    # TODO:
    #   booking = db.query(Booking).filter(Booking.payment_session_id == session_id).first()
    #   if not booking → raise HTTPException(404, "Booking not found")
    #
    #   SELECT FOR UPDATE inventory rows
    #   For each:
    #       reserved_count = max(0, reserved_count - booking.rooms_count)
    #       book_count += booking.rooms_count
    #
    #   booking.booking_status = CONFIRMED
    #   db.commit()
    pass
