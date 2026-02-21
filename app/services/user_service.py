from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.user import User
from app.models.guest import Guest
from app.models.booking import Booking
from app.schemas.user import ProfileUpdateRequest
from app.database import get_all, update_record, get_by_id, create_record, delete_record


def get_profile(current_user: User):
    # TODO: Return the current_user ORM object (router will serialize via UserOut)
    pass


def update_profile(db: Session, current_user: User, data: ProfileUpdateRequest) -> User:
    # TODO: update_record(db, current_user, **data.model_dump(exclude_none=True))
    # Hint: exclude_none=True ensures only provided fields are updated (PATCH semantics)
    pass


def get_my_bookings(db: Session, current_user: User):
    # TODO: return get_all(db, Booking, user_id=current_user.id)
    pass


def get_guests(db: Session, current_user: User):
    # TODO: return get_all(db, Guest, user_id=current_user.id)
    pass


def add_guest(db: Session, current_user: User, data) -> Guest:
    # TODO: create_record(db, Guest, user_id=current_user.id, name=data.name, gender=data.gender, age=data.age)
    pass


def update_guest(db: Session, guest_id: int, current_user: User, data) -> Guest:
    # TODO:
    #   guest = get_by_id(db, Guest, guest_id) → 404 if not found
    #   if guest.user_id != current_user.id → raise HTTPException(403, "Not your guest")
    #   return update_record(db, guest, **data.model_dump(exclude_none=True, exclude={"id"}))
    pass


def delete_guest(db: Session, guest_id: int, current_user: User) -> None:
    # TODO:
    #   guest = get_by_id(db, Guest, guest_id) → 404 if not found
    #   if guest.user_id != current_user.id → raise HTTPException(403, "Not your guest")
    #   delete_record(db, guest)
    pass
