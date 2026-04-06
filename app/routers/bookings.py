from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, get_by_id
from app.models.user import User
from app.models.booking import Booking
from app.schemas.booking import BookingRequest, BookingOut, BookingStatusResponse, BookingPaymentInitResponse
from app.schemas.guest import GuestSchema
from app.security.guards import get_current_user
from app.services import booking_service
from typing import List

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("/init", response_model=BookingOut, status_code=201)
def init_booking(
    data: BookingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    POST /bookings/init — status 201 Created.

    Initiates a new booking. The service handles all the complex logic:
      - Validating hotel and room existence
      - SELECT FOR UPDATE to prevent double-booking
      - Incrementing reserved_count on inventory rows
      - Dynamic price calculation across all dates

    The router just needs to pass `data`, `db`, and `current_user` to the service.

    Notice that BookingRequest is now properly imported — the original file had a TODO
    to add this import. Make sure it's in the imports above.
    """
    return booking_service.init_booking(db, data, current_user)


@router.post("/{booking_id}/addGuests", response_model=BookingOut)
def add_guests(
    booking_id: int,
    guest_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    POST /bookings/{booking_id}/addGuests

    Attaches a list of saved guest IDs to a booking.
    `guest_ids` is a JSON array body (e.g. [1, 2, 3]).

    The service enforces: ownership → expiry → status (must be RESERVED).
    If any check fails, the service raises the appropriate HTTPException.

    Pattern: call service → return result.
    """
    return booking_service.add_guests(db, booking_id, guest_ids, current_user)


@router.post("/{booking_id}/payments", response_model=BookingPaymentInitResponse)
def initiate_payment(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    POST /bookings/{booking_id}/payments

    Creates a Stripe Checkout session and returns the payment URL.
    The service handles all Stripe API calls and state transitions.

    response_model=BookingPaymentInitResponse — what field does that schema have?
    The service returns a URL string — how do you wrap that into the response schema?
    """
    payment_url = booking_service.initiate_payment(db, booking_id, current_user)
    return BookingPaymentInitResponse(payment_url=payment_url)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    POST /bookings/{booking_id}/cancel

    Cancels a confirmed booking: releases inventory and issues a Stripe refund.
    The service enforces: ownership → status must be CONFIRMED.

    Pattern: call service → return result.
    """
    return booking_service.cancel_booking(db, booking_id, current_user)


@router.get("/{booking_id}/status", response_model=BookingStatusResponse)
def booking_status(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GET /bookings/{booking_id}/status

    Returns just the booking_status field of a booking.
    This is a lightweight polling endpoint — used by the frontend to check
    whether a payment has been confirmed by the webhook.

    Steps:
      1. Fetch the booking by ID → 404 if not found
      2. Check ownership → 403 if not theirs
      3. Return BookingStatusResponse(booking_status=booking.booking_status)

    Notice: no expiry check here — the user can always look up the status.
    This is thin enough that you could implement it directly in the router
    OR delegate it to the service. Either approach is fine.
    """
    booking = get_by_id(db, Booking, booking_id)
    if not booking:
        raise HTTPException(404, f"Booking not found: {booking_id}")
    if booking.user_id != current_user.id:
        raise HTTPException(403, "You do not own this booking")
    return BookingStatusResponse(booking_status=booking.booking_status)
