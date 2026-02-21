from sqlalchemy.orm import Session
from app.models.guest import Guest
from app.models.user import User
from app.database import get_by_id, get_all, create_record, update_record, delete_record
from fastapi import HTTPException


def get_user_guests(db: Session, current_user: User):
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
