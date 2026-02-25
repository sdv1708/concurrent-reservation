from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.user import User
from app.models.guest import Guest
from app.models.booking import Booking
from app.schemas.user import ProfileUpdateRequest
from app.database import get_all, update_record, get_by_id, create_record, delete_record


def get_profile(current_user: User):
    """
    Return the current user's profile.

    You already have the user object — FastAPI injected it via Depends(get_current_user).
    The router's response_model (UserOut) will handle the ORM → schema conversion
    automatically, so you just need to return the raw ORM object here.

    No database query needed — why not?
    """
    return current_user


def update_profile(db: Session, current_user: User, data: ProfileUpdateRequest) -> User:
    """
    Apply a partial update to the current user's profile (PATCH semantics).

    Key concept — PATCH vs PUT:
      - PUT replaces the whole object (requires every field)
      - PATCH only replaces fields that were actually sent
      Think about how model_dump() can help you send ONLY the non-null fields.

    Which database helper is the right one here?
    Look at the Quick Reference table in PLAYBOOK.md — you want the one that
    updates an existing instance, commits, and refreshes it.

    What does **kwargs unpacking do when you pass a dict to it?
    """
    updated_record = None
    if get_profile(current_user): 
        updated_record = update_record(db, current_user, **data.model_dump())
    else: 
        raise HTTPException(401, "User Does not exist")
    
    return updated_record

def get_my_bookings(db: Session, current_user: User):
    """
    Return all bookings that belong to the currently logged-in user.

    Think about: what column on the Booking model links a booking to a user?
    Which database helper returns all rows matching a filter condition?
    How do you pass that filter so only THIS user's bookings come back?
    """
    return get_all(db, Booking, user_id=current_user.id)
    

def get_guests(db: Session, current_user: User):
    """
    Return all guest profiles saved by the currently logged-in user.

    Same pattern as get_my_bookings — which column on Guest connects it to a user?
    Use the same helper, just with a different model and filter.
    """
    guest = None
    if get_profile(current_user): 
        guest = get_all(db, Guest, user_id=current_user.id)
    else: 
        raise HTTPException(401, "User Does not exist")
    
    return guest


def add_guest(db: Session, current_user: User, data) -> Guest:
    """
    Create a new Guest record and associate it with the current user.

    Important: the user_id on the new guest must be set to current_user.id
    so that ownership is established at creation time.
    Never trust the client to send user_id — always set it server-side.

    Which helper inserts a new record, commits, and returns the new object?
    What fields does the Guest model need? (Check app/models/guest.py)
    """
    guest = None
    if get_profile(current_user): 
        guest = create_record(db, Guest, user_id=current_user.id, name=data.name,
                              gender=data.gender, age=data.age)
    else: 
        raise HTTPException(401, "User Does not exist")
    
    return guest


def update_guest(db: Session, guest_id: int, current_user: User, data) -> Guest:
    """
    Update a guest's details — but only if the guest belongs to this user.

    Steps to think through:
      1. Fetch the guest by its primary key. What do you do if it doesn't exist?
      2. Verify ownership: does guest.user_id match current_user.id?
         If not → what HTTP status code means "you don't have permission"?
      3. Apply the update using PATCH semantics.
         Should you allow the client to change the guest's `id` field? How do you exclude it?

    Look at the ownership check pattern in Phase 5 of PLAYBOOK.md for reference.
    """
    guest = get_by_id(db, Guest, guest_id)
    if not guest: 
        raise HTTPException(404, f"Guest Not Found: {guest_id}")
    if guest.user_id != current_user.id: 
        raise HTTPException(403, f"Only users can update guests")
    return update_record(db, guest, **data.model_dump(exclude_none=True, exclude={'id'}))
    
    
def delete_guest(db: Session, guest_id: int, current_user: User) -> None:
    """
    Delete a guest — but only if the guest belongs to this user.

    Steps to think through:
      1. Fetch the guest by ID → what happens if it's not found?
      2. Check ownership → same pattern as update_guest above
      3. Which helper deletes a record and commits?

    Return type is None — what does that mean for what you return (or don't)?
    """
    guest = get_by_id(db, Guest, guest_id)
    if not guest: 
        raise HTTPException(404, f"Guest not found: {guest_id}")
    if guest.id != current_user.id: 
        raise HTTPException(403, "Only your own guests can be deleted")
    delete_record(db, guest)
