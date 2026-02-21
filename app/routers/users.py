from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserOut, ProfileUpdateRequest
from app.schemas.guest import GuestSchema
from app.security.guards import get_current_user
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    # TODO: Return current_user wrapped in UserOut
    # Hint: return UserOut.model_validate(current_user)
    pass


@router.patch("/profile", response_model=UserOut)
def update_profile(
    data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call user_service.update_profile(db, current_user, data)
    # Hint: use update_record(db, current_user, **data.model_dump(exclude_none=True))
    pass


@router.get("/myBookings")
def my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call user_service.get_my_bookings(db, current_user)
    # Hint: return get_all(db, Booking, user_id=current_user.id)
    pass


@router.get("/guests", response_model=list[GuestSchema])
def list_guests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call user_service.get_guests(db, current_user)
    # Hint: return get_all(db, Guest, user_id=current_user.id)
    pass


@router.post("/guests", response_model=GuestSchema, status_code=201)
def add_guest(
    data: GuestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call user_service.add_guest(db, current_user, data)
    # Hint: use create_record(db, Guest, user_id=current_user.id, **data.model_dump(exclude={"id"}))
    pass


@router.put("/guests/{guest_id}", response_model=GuestSchema)
def update_guest(
    guest_id: int,
    data: GuestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call user_service.update_guest(db, guest_id, current_user, data)
    # Hint: fetch guest, check guest.user_id == current_user.id (403 if not), then update_record
    pass


@router.delete("/guests/{guest_id}", status_code=204)
def delete_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call user_service.delete_guest(db, guest_id, current_user)
    # Hint: fetch guest, check ownership, then delete_record(db, guest)
    pass
