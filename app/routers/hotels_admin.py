from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.hotel import HotelSchema
from app.schemas.booking import HotelReportOut
from app.security.guards import require_hotel_manager
from app.services import hotel_service

# dependencies=[...] applies require_hotel_manager to EVERY route in this router
router = APIRouter(
    prefix="/admin/hotels",
    tags=["Hotel Admin"],
    dependencies=[Depends(require_hotel_manager)],
)


@router.post("", response_model=HotelSchema, status_code=201)
def create_hotel(
    data: HotelSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    REFERENCE for how admin routes work:
    - Guard is on the router, AND we Depends on it here to get the User object
    - Service does the actual work
    - Router just returns the schema-validated response
    """
    hotel = hotel_service.create_hotel(db, data, current_user)
    return HotelSchema.model_validate(hotel)


@router.get("", response_model=list[HotelSchema])
def list_my_hotels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call hotel_service.get_my_hotels(db, current_user)
    pass


@router.get("/{hotel_id}", response_model=HotelSchema)
def get_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call hotel_service.get_hotel(db, hotel_id, current_user)
    # Hint: get_by_id(db, Hotel, hotel_id) → check owner → return schema
    pass


@router.put("/{hotel_id}", response_model=HotelSchema)
def update_hotel(
    hotel_id: int,
    data: HotelSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call hotel_service.update_hotel(db, hotel_id, data, current_user)
    # Hint: fetch hotel → check ownership → update_record(db, hotel, **data.model_dump(exclude_none=True))
    pass


@router.delete("/{hotel_id}", status_code=204)
def delete_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call hotel_service.delete_hotel(db, hotel_id, current_user)
    # Hint: fetch hotel → check ownership → delete_record(db, hotel)
    pass


@router.patch("/{hotel_id}/activate", response_model=HotelSchema)
def activate_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call hotel_service.activate_hotel(db, hotel_id, current_user)
    # Hint: update_record(db, hotel, active=True)
    pass


@router.get("/{hotel_id}/bookings")
def hotel_bookings(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call hotel_service.get_hotel_bookings(db, hotel_id, current_user)
    # Hint: get_all(db, Booking, hotel_id=hotel_id) — check ownership first
    pass


@router.get("/{hotel_id}/reports", response_model=HotelReportOut)
def hotel_report(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call hotel_service.get_report(db, hotel_id, start_date, end_date, current_user)
    # Query params: start_date (default: 1 month ago), end_date (default: today)
    # Hint: filter Booking by hotel_id + CONFIRMED status + date range → count + sum amounts
    pass
