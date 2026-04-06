from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.user import User
from app.models.guest import Guest
from app.models.booking import Booking
from app.schemas.user import ProfileUpdateRequest
from app.database import get_all, update_record, get_by_id, create_record, delete_record


def get_profile(current_user: User):
    """Retrieves the authenticated user's profile.

    Args:
        current_user (User): The authenticated user instance.

    Returns:
        User: The user instance.
    """
    return current_user


def update_profile(db: Session, current_user: User, data: ProfileUpdateRequest) -> User:
    """Applies a partial update to the authenticated user's profile.

    Args:
        db (Session): The database session.
        current_user (User): The authenticated user making the update.
        data (ProfileUpdateRequest): The fields to partially update.

    Returns:
        User: The updated user record.

    Raises:
        HTTPException: If the user context is invalid (401).
    """
    updated_record = None
    if get_profile(current_user): 
        updated_record = update_record(db, current_user, **data.model_dump())
    else: 
        raise HTTPException(401, "User Does not exist")
    
    return updated_record

def get_my_bookings(db: Session, current_user: User):
    """Retrieves all bookings belonging to the authenticated user.

    Args:
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        list[Booking]: A list of the user's bookings.
    """
    return get_all(db, Booking, user_id=current_user.id)
    

def get_guests(db: Session, current_user: User):
    """Retrieves all guest profiles saved by the authenticated user.

    Args:
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        list[Guest]: A list of the user's saved guests.

    Raises:
        HTTPException: If the user context is invalid (401).
    """
    guest = None
    if get_profile(current_user): 
        guest = get_all(db, Guest, user_id=current_user.id)
    else: 
        raise HTTPException(401, "User Does not exist")
    
    return guest


def add_guest(db: Session, current_user: User, data) -> Guest:
    """Creates a new guest profile associated with the authenticated user.

    Args:
        db (Session): The database session.
        current_user (User): The authenticated user.
        data (GuestSchema): The guest's details.

    Returns:
        Guest: The newly created guest record.

    Raises:
        HTTPException: If the user context is invalid (401).
    """
    guest = None
    if get_profile(current_user): 
        guest = create_record(db, Guest, user_id=current_user.id, name=data.name,
                              gender=data.gender, age=data.age)
    else: 
        raise HTTPException(401, "User Does not exist")
    
    return guest


def update_guest(db: Session, guest_id: int, current_user: User, data) -> Guest:
    """Updates an existing guest record after verifying ownership.

    Args:
        db (Session): The database session.
        guest_id (int): The ID of the guest to update.
        current_user (User): The authenticated user.
        data (GuestSchema): The updated guest details.

    Returns:
        Guest: The updated guest record.

    Raises:
        HTTPException: If the guest is not found (404) or not owned by the user (403).
    """
    guest = get_by_id(db, Guest, guest_id)
    if not guest: 
        raise HTTPException(404, f"Guest Not Found: {guest_id}")
    if guest.user_id != current_user.id: 
        raise HTTPException(403, f"Only users can update guests")
    return update_record(db, guest, **data.model_dump(exclude_none=True, exclude={'id'}))
    
    
def delete_guest(db: Session, guest_id: int, current_user: User) -> None:
    """Deletes a guest record after verifying ownership.

    Args:
        db (Session): The database session.
        guest_id (int): The ID of the guest to delete.
        current_user (User): The authenticated user.

    Raises:
        HTTPException: If the guest is not found (404) or not owned by the user (403).
    """
    guest = get_by_id(db, Guest, guest_id)
    if not guest: 
        raise HTTPException(404, f"Guest not found: {guest_id}")
    if guest.user_id != current_user.id: 
        raise HTTPException(403, "Only your own guests can be deleted")
    delete_record(db, guest)
