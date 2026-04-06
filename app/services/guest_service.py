from sqlalchemy.orm import Session
from app.models.guest import Guest
from app.models.user import User
from app.database import get_by_id, get_all, create_record, update_record, delete_record
from fastapi import HTTPException


def get_user_guests(db: Session, current_user: User):
    """
    Return all guests created by this user.

    Guests are personal — each user only sees their own saved guests.
    Which column on Guest links it to its owner?
    Which helper returns all rows matching a single filter?
    """
    pass


def add_guest(db: Session, current_user: User, data) -> Guest:
    """
    Create a new guest and associate it with the current user.

    The user_id MUST be set to current_user.id server-side — never let the client
    send a user_id (that would be a security hole).

    What fields does the Guest model have? (Check app/models/guest.py)
    Which helper inserts a new row, commits, and returns the instance?
    """
    pass


def update_guest(db: Session, guest_id: int, current_user: User, data) -> Guest:
    """
    Update a guest — only if it belongs to the current user.

    Three things to check in order:
      1. Does the guest exist? → 404 if not
      2. Does it belong to this user? (guest.user_id == current_user.id) → 403 if not
      3. Apply the update with PATCH semantics

    Should you allow the update to change the guest's `id`? Exclude it if not.
    """
    pass


def delete_guest(db: Session, guest_id: int, current_user: User) -> None:
    """
    Delete a guest — only if it belongs to the current user.

    Same ownership pattern as update_guest: check existence first, then ownership.
    Which helper deletes a record and commits the transaction?
    """
    pass
