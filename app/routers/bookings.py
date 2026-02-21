from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.booking import BookingOut, BookingStatusResponse, BookingPaymentInitResponse
from app.schemas.guest import GuestSchema
from app.security.guards import get_current_user
from app.services import booking_service
from typing import List

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("/init", response_model=BookingOut, status_code=201)
def init_booking(
    data,  # TODO: import BookingRequest from app.schemas.booking and use it here
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call booking_service.init_booking(db, data, current_user)
    #
    # CRITICAL — booking init must use SELECT FOR UPDATE:
    #   rows = db.execute(
    #       select(Inventory)
    #       .where(
    #           Inventory.room_id == data.room_id,
    #           Inventory.date.between(data.check_in_date, data.check_out_date),
    #           Inventory.closed == False,
    #           (Inventory.total_count - Inventory.book_count - Inventory.reserved_count) >= data.rooms_count,
    #       )
    #       .with_for_update()    ← pessimistic lock — prevents double booking
    #   ).scalars().all()
    #
    # If len(rows) != days → raise 400 "Room not available"
    # For each row: reserved_count += rooms_count
    # price = calculate_total_price(rows) * rooms_count
    # INSERT Booking(status=RESERVED, amount=price)
    # COMMIT
    pass


@router.post("/{booking_id}/addGuests", response_model=BookingOut)
def add_guests(
    booking_id: int,
    guest_ids: List[int],   # list of existing guest IDs to attach to this booking
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call booking_service.add_guests(db, booking_id, guest_ids, current_user)
    # State rules:
    #   - Check has_booking_expired(booking) → raise 400 if expired
    #   - Only allowed when booking.status == RESERVED → raise 400 otherwise
    #   - Check booking.user_id == current_user.id → raise 403 otherwise
    #   - Attach guests: booking.guests = [fetched Guest objects]
    #   - Set booking.status = GUESTS_ADDED
    pass


@router.post("/{booking_id}/payments", response_model=BookingPaymentInitResponse)
def initiate_payment(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call booking_service.initiate_payment(db, booking_id, current_user)
    # State rules:
    #   - Check has_booking_expired(booking) → raise 400 if expired
    #   - Allowed from RESERVED or GUESTS_ADDED → raise 400 otherwise
    #   - Check ownership → raise 403 otherwise
    #   - Create Stripe checkout session (see architecture §12)
    #   - Store session.id in booking.payment_session_id
    #   - Set booking.status = PAYMENTS_PENDING
    #   - Return { payment_url: session.url }
    pass


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call booking_service.cancel_booking(db, booking_id, current_user)
    # State rules:
    #   - Only allowed when booking.status == CONFIRMED → raise 400 otherwise
    #   - Check ownership → raise 403 otherwise
    #   - SELECT FOR UPDATE inventory rows → decrement book_count
    #   - Issue Stripe refund: stripe.Refund.create(payment_intent=session.payment_intent)
    #   - Set booking.status = CANCELLED
    pass


@router.get("/{booking_id}/status", response_model=BookingStatusResponse)
def booking_status(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Fetch booking, check ownership, return BookingStatusResponse(booking_status=booking.booking_status)
    # Note: no expiry check needed here — status check is always allowed
    pass
