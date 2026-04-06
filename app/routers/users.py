from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserOut, ProfileUpdateRequest
from app.schemas.guest import GuestSchema
from app.security.guards import get_current_user
from app.services import user_service
import logging

router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger(__name__)

@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    """Retrieves the authenticated user's profile.
    
    Args:
        current_user (User): The authenticated user instance.

    Returns:
        UserOut: The user's profile data.
    """

    return user_service.get_profile(current_user)


@router.patch("/profile", response_model=UserOut)
def update_profile(
    data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates the authenticated user's profile.
    
    Performs a partial update, modifying only the fields provided.
    
    Args:
        data (ProfileUpdateRequest): The fields to update.
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        UserOut: The updated user profile.
    """
    return user_service.update_profile(db, current_user, data)


@router.get("/myBookings")
def my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves all bookings made by the authenticated user.
    
    Args:
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        list[Booking]: A list of the user's bookings.
    """
    return user_service.get_my_bookings(db, current_user)


@router.get("/guests", response_model=list[GuestSchema])
def list_guests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves all guest profiles saved by the authenticated user.
    
    Args:
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        list[GuestSchema]: A list of saved guests.
    """
    return user_service.get_guests(db, current_user)


@router.post("/guests", response_model=GuestSchema, status_code=201)
def add_guest(
    data: GuestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a new guest associated with the authenticated user.
    
    Args:
        data (GuestSchema): The guest's details.
        db (Session): The database session.
        current_user (User): The authenticated user making the request.

    Returns:
        GuestSchema: The created guest record.
    """
    return user_service.add_guest(db, current_user, data)


@router.put("/guests/{guest_id}", response_model=GuestSchema)
def update_guest(
    guest_id: int,
    data: GuestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates an existing guest's details.
    
    Args:
        guest_id (int): The ID of the guest to update.
        data (GuestSchema): The updated guest details.
        db (Session): The database session.
        current_user (User): The authenticated user owning the guest record.

    Returns:
        GuestSchema: The updated guest record.
    """
    return user_service.update_guest(db, guest_id, current_user, data)


@router.delete("/guests/{guest_id}", status_code=204)
def delete_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a guest from the authenticated user's profile.
    
    Args:
        guest_id (int): The ID of the guest to delete.
        db (Session): The database session.
        current_user (User): The authenticated user trying to perform the deletion.
    """
    user_service.delete_guest(db, guest_id, current_user)
    return None
