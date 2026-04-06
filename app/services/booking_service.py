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
    """Determines if a booking's 10-minute temporary payment window has expired.

    Args:
        booking (Booking): The booking to check.

    Returns:
        bool: True if expired, False otherwise.
    """
    
    created = booking.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > created + timedelta(minutes=10)


def init_booking(db: Session, data: BookingRequest, current_user: User) -> Booking:
    """Initiates a new booking with pessimistic locking to prevent double-booking.

    Locks the requested inventory rows, applies a temporary hold via `reserved_count`,
    and calculates dynamic total pricing.

    Args:
        db (Session): The database session.
        data (BookingRequest): Booking details (hotel, room, dates, counts).
        current_user (User): The user making the booking.

    Returns:
        Booking: The created RESERVED booking.

    Raises:
        HTTPException: If the hotel/room is not found (404), or if the room 
                       is unavailable for the requested dates (400).
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
    """Attaches a list of guest profiles to a booking.

    Args:
        db (Session): The database session.
        booking_id (int): ID of the booking.
        guest_ids (list[int]): List of guest IDs to attach.
        current_user (User): The authenticated user making the request.

    Returns:
        Booking: The updated booking reflecting the attached guests.

    Raises:
        HTTPException: If the booking is not found (404), not owned by the user (403), 
                       has expired (400), or is not in RESERVED status (400).
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
    """Creates a Stripe Checkout session and transitions the booking to PAYMENTS_PENDING.

    Args:
        db (Session): The database session.
        booking_id (int): The ID of the booking.
        current_user (User): The authenticated user.

    Returns:
        str: The generated Stripe Checkout URL.

    Raises:
        HTTPException: If the booking is not found (404), not owned by the user (403),
                       expired (400), or in an invalid state for payment (400).
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
    """Cancels a confirmed booking, releases inventory, and issues a Stripe refund.

    Args:
        db (Session): The database session.
        booking_id (int): The ID of the booking to cancel.
        current_user (User): The authenticated user making the cancellation request.

    Returns:
        Booking: The cancelled booking record.

    Raises:
        HTTPException: If the booking is not found (404), not owned by the user (403), 
                       or not in a CONFIRMED state (400).
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
    """Finalizes a booking upon successful payment via Stripe webhook.

    Transitions inventory holds into confirmed bookings and updates the booking status.
    Uses pessimistic locking to handle concurrent webhook deliveries.

    Args:
        db (Session): The database session.
        session_id (str): The Stripe checkout session ID.

    Raises:
        HTTPException: If the booking associated with the session ID is not found (404).
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
