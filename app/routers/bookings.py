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
    """Initiates a new booking.
    
    Validates hotel and room existence, locks inventory to prevent double-booking, 
    and applies a temporary reservation hold based on dynamic pricing.
    
    Args:
        data (BookingRequest): The booking details (hotel, room, dates, count).
        db (Session): The database session.
        current_user (User): The authenticated user making the booking.

    Returns:
        BookingOut: The newly created booking in RESERVED status.
    """
    return booking_service.init_booking(db, data, current_user)


@router.post("/{booking_id}/addGuests", response_model=BookingOut)
def add_guests(
    booking_id: int,
    guest_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attaches a list of saved guests to an existing booking.
    
    Args:
        booking_id (int): The ID of the primary booking.
        guest_ids (List[int]): A list of guest IDs to attach.
        db (Session): The database session.
        current_user (User): The authenticated user making the request.

    Returns:
        BookingOut: The updated booking reflecting the attached guests.
    """
    return booking_service.add_guests(db, booking_id, guest_ids, current_user)


@router.post("/{booking_id}/payments", response_model=BookingPaymentInitResponse)
def initiate_payment(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a Stripe Checkout session for the booking.
    
    Args:
        booking_id (int): The ID of the booking to pay for.
        db (Session): The database session.
        current_user (User): The authenticated user initiating payment.

    Returns:
        BookingPaymentInitResponse: Contains the Stripe checkout URL.
    """
    payment_url = booking_service.initiate_payment(db, booking_id, current_user)
    return BookingPaymentInitResponse(payment_url=payment_url)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancels a confirmed booking.
    
    Releases the locked inventory and issues a refund via Stripe APIs.
    
    Args:
        booking_id (int): The ID of the booking to cancel.
        db (Session): The database session.
        current_user (User): The authenticated user requesting cancellation.

    Returns:
        BookingOut: The cancelled booking details.
    """
    return booking_service.cancel_booking(db, booking_id, current_user)


@router.get("/{booking_id}/status", response_model=BookingStatusResponse)
def booking_status(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves the current status of a user's booking.
    
    This lightweight polling endpoint checks whether a payment has been 
    successfully captured and finalized by the webhook.
    
    Args:
        booking_id (int): The ID of the booking.
        db (Session): The database session.
        current_user (User): The authenticated user checking the status.

    Returns:
        BookingStatusResponse: Information containing the booking's status.
    """
    booking = get_by_id(db, Booking, booking_id)
    if not booking:
        raise HTTPException(404, f"Booking not found: {booking_id}")
    if booking.user_id != current_user.id:
        raise HTTPException(403, "You do not own this booking")
    return BookingStatusResponse(booking_status=booking.booking_status)
