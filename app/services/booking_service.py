from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
import stripe
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.user import User
from app.models.enums import BookingStatusEnum
from app.schemas.booking import BookingRequest
from app.pricing.pricing_service import calculate_total_price
from app.services import stay_inventory
from app.services.stay_inventory import Stay, StayUnavailableError
from app.database import get_by_id
from app.config import settings

# The payment window of a hold. After it runs out, the hold can be released.
HOLD_WINDOW = timedelta(minutes=10)

# The booking states in which the booking has a hold in reserved_count.
HOLD_STATES = (
    BookingStatusEnum.RESERVED,
    BookingStatusEnum.GUESTS_ADDED,
    BookingStatusEnum.PAYMENTS_PENDING,
)


def has_booking_expired(booking: Booking, now: datetime | None = None) -> bool:
    """Determines if a booking's 10-minute temporary payment window has expired.

    Args:
        booking (Booking): The booking to check.
        now (datetime | None): The current time in UTC. None means the clock time.

    Returns:
        bool: True if expired, False otherwise.
    """
    now = now or datetime.now(timezone.utc)
    created = booking.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return now > created + HOLD_WINDOW


def _stay_of(booking: Booking) -> Stay:
    return Stay(booking.check_in_date, booking.check_out_date)


def _lock_booking(db: Session, booking_id: int) -> Booking | None:
    """Lock and return the booking row, or None if it does not exist.

    Every function that changes a booking's status locks the row first and
    then reads the status. Two such functions on one booking thus run one
    after the other, and the second one sees the status that the first set.
    """
    return db.execute(
        select(Booking).where(Booking.id == booking_id).with_for_update()
    ).scalars().first()


def _expired_hold_ids(
    db: Session, now: datetime, room_type_id: int | None = None, stay: Stay | None = None
) -> list[int]:
    """Return the ids of the bookings that have a hold whose payment window ran out.

    The query does not lock. `expire_hold` locks each booking and checks it
    again. With `room_type_id` and `stay`, the query returns only the bookings
    of that room type whose stay shares a night with `stay`.
    """
    # created_at is stored in UTC without a time zone.
    cutoff = (now - HOLD_WINDOW).astimezone(timezone.utc).replace(tzinfo=None)
    stmt = select(Booking.id).where(
        Booking.booking_status.in_(HOLD_STATES),
        Booking.created_at < cutoff,
    )
    if room_type_id is not None:
        stmt = stmt.where(
            Booking.room_id == room_type_id,
            Booking.check_in_date < stay.check_out,
            Booking.check_out_date > stay.check_in,
        )
    return list(db.execute(stmt.order_by(Booking.id)).scalars().all())


def expire_hold(db: Session, booking_id: int, now: datetime | None = None) -> bool:
    """Releases the hold of one booking whose payment window ran out, and sets
    the booking to EXPIRED. Commits once.

    The function locks the booking row before it reads the status, as
    `confirm_booking` does. If the Stripe webhook confirms the same booking
    at the same time, one of the two waits for the other:
      * The release goes first: the booking is EXPIRED when the webhook reads
        it, and `confirm_booking` tries to hold the stay again.
      * The webhook goes first: the booking is CONFIRMED when this function
        reads it, so this function changes nothing.

    Each call is one transaction that locks one booking and the rows of one
    stay. A call thus never holds the rows of two stays at once, and the
    date-order rule of `stay_inventory` keeps it free of deadlocks.

    Args:
        db (Session): The database session.
        booking_id (int): The ID of the booking.
        now (datetime | None): The current time in UTC. None means the clock time.

    Returns:
        bool: True if the function released the hold. False if the booking does
              not exist, has no hold, or its payment window did not run out.
              A second call on the same booking thus changes nothing.
    """
    booking = _lock_booking(db, booking_id)
    released = (
        booking is not None
        and booking.booking_status in HOLD_STATES
        and has_booking_expired(booking, now)
    )
    if released:
        stay_inventory.release_hold(db, booking.room_id, _stay_of(booking), booking.rooms_count)
        booking.booking_status = BookingStatusEnum.EXPIRED
    # Commit on both paths, so that the row lock ends here.
    db.commit()
    return released


def release_expired_holds(db: Session, now: datetime | None = None) -> int:
    """Releases every hold whose payment window ran out.

    The periodic job (scripts/release_expired_holds.py) calls this function.
    Each booking is released in its own transaction. See `expire_hold`.

    Args:
        db (Session): The database session.
        now (datetime | None): The current time in UTC. None means the clock time.

    Returns:
        int: The number of holds that this call released.
    """
    now = now or datetime.now(timezone.utc)
    return sum(expire_hold(db, booking_id, now) for booking_id in _expired_hold_ids(db, now))


def init_booking(db: Session, data: BookingRequest, current_user: User) -> Booking:
    """Places a hold for the stay and creates a RESERVED booking.

    The hold and the new booking commit in one transaction. Before the hold,
    the function releases the expired holds of the same room type that share
    a night with the stay. Each of those releases commits on its own.

    Args:
        db (Session): The database session.
        data (BookingRequest): Booking details (hotel, room type, stay, room count).
        current_user (User): The user making the booking.

    Returns:
        Booking: The created RESERVED booking.

    Raises:
        HTTPException: If the hotel is not found or not active, or the room
                       type is not found in that hotel (404).
        StayUnavailableError: If the room type does not have enough available
                              rooms on every night of the stay (mapped to 409).
    """
    from app.models.hotel import Hotel
    from app.models.room import Room

    hotel = get_by_id(db, Hotel, data.hotel_id)
    if not hotel or not hotel.active:
        raise HTTPException(404, f"Hotel not found or not active: {data.hotel_id}")

    room = get_by_id(db, Room, data.room_id)
    if not room or room.hotel_id != hotel.id:
        raise HTTPException(404, f"Room {data.room_id} not found in hotel {data.hotel_id}")

    stay = Stay(data.check_in_date, data.check_out_date)

    # Lazy release: free the expired holds that share a night with this stay,
    # so that they cannot block this hold if the periodic job did not run yet.
    # Each release commits on its own, before this hold locks any row.
    now = datetime.now(timezone.utc)
    for expired_id in _expired_hold_ids(db, now, data.room_id, stay):
        expire_hold(db, expired_id, now)

    held_nights = stay_inventory.place_hold(db, data.room_id, stay, data.rooms_count)

    # Calculate price: per-room total × number of rooms
    price_per_room = calculate_total_price(held_nights)
    total_price = price_per_room * data.rooms_count

    booking = Booking(
        hotel_id=data.hotel_id,
        room_id=data.room_id,
        user_id=current_user.id,
        rooms_count=data.rooms_count,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        booking_status=BookingStatusEnum.RESERVED,
        amount=total_price,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
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
        HTTPException: If the booking or a guest is not found (404), the booking
                       or a guest is not owned by the user (403), the booking
                       has expired (400), or is not in RESERVED status (400).
    """
    # Lock the booking row, so that a concurrent release of the expired hold
    # cannot change the status between the checks below and the commit.
    booking = _lock_booking(db, booking_id)
    if not booking:
        raise HTTPException(404, f"Booking not found: {booking_id}")
    if booking.user_id != current_user.id:
        raise HTTPException(403, "You do not own this booking")
    if has_booking_expired(booking):
        raise HTTPException(400, "Booking has expired")
    if booking.booking_status != BookingStatusEnum.RESERVED:
        raise HTTPException(400, f"Cannot add guests to a booking with status: {booking.booking_status}")

    guests = []
    for gid in guest_ids:
        guest = get_by_id(db, Guest, gid)
        if not guest:
            raise HTTPException(404, f"Guest not found: {gid}")
        if guest.user_id != current_user.id:
            raise HTTPException(403, f"You do not own guest {gid}")
        guests.append(guest)
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
    # Lock the booking row, so that a concurrent release of the expired hold
    # cannot change the status between the checks below and the commit.
    booking = _lock_booking(db, booking_id)
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
    """Cancels a confirmed booking, releases its booked rooms, and issues a Stripe refund.

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

    stay_inventory.release_booked(
        db, booking.room_id, Stay(booking.check_in_date, booking.check_out_date), booking.rooms_count
    )

    # Stripe refund against the original payment intent
    stripe_session = stripe.checkout.Session.retrieve(booking.payment_session_id)
    stripe.Refund.create(payment_intent=stripe_session.payment_intent)

    booking.booking_status = BookingStatusEnum.CANCELLED
    db.commit()
    return booking


def confirm_booking(db: Session, session_id: str) -> None:
    """Finalizes a booking upon successful payment via Stripe webhook.

    What the function does depends on the booking status:
      * RESERVED, GUESTS_ADDED, or PAYMENTS_PENDING: the hold still exists,
        even if its payment window ran out. The function turns the hold into
        booked rooms and sets the booking to CONFIRMED.
      * EXPIRED: the hold was released, but the guest paid. The function
        places a new hold for the same stay and books it at the paid amount.
        If the stay is unavailable, or a night of it is closed, the function
        refunds the payment through Stripe and sets the booking to CANCELLED.
      * CONFIRMED or CANCELLED: nothing changes. A repeated Stripe webhook
        thus does not add booked rooms twice and does not refund twice.

    Args:
        db (Session): The database session.
        session_id (str): The Stripe checkout session ID.

    Raises:
        HTTPException: If the booking associated with the session ID is not found (404).
    """
    # Lock the booking row, so that two concurrent webhook deliveries, or a
    # webhook delivery and a release of the expired hold, cannot both pass
    # the status check below.
    booking = db.execute(
        select(Booking).where(Booking.payment_session_id == session_id).with_for_update()
    ).scalars().first()
    if not booking:
        raise HTTPException(404, f"Booking not found for session: {session_id}")
    if booking.booking_status in (BookingStatusEnum.CONFIRMED, BookingStatusEnum.CANCELLED):
        return

    stay = _stay_of(booking)
    if booking.booking_status == BookingStatusEnum.EXPIRED:
        try:
            stay_inventory.place_hold(db, booking.room_id, stay, booking.rooms_count)
        except StayUnavailableError:
            _refund_late_payment(booking)
            booking.booking_status = BookingStatusEnum.CANCELLED
            db.commit()
            return

    stay_inventory.book_hold(db, booking.room_id, stay, booking.rooms_count)

    booking.booking_status = BookingStatusEnum.CONFIRMED
    db.commit()


def _refund_late_payment(booking: Booking) -> None:
    """Refunds the payment of a booking whose hold was released before payment.

    The idempotency key makes Stripe create one refund only, if a webhook
    retry calls this function again within 24 hours.
    """
    stripe_session = stripe.checkout.Session.retrieve(booking.payment_session_id)
    stripe.Refund.create(
        payment_intent=stripe_session.payment_intent,
        idempotency_key=f"late-payment-refund-{booking.id}",
    )
