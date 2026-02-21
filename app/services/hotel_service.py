from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from datetime import date, timedelta
from app.models.hotel import Hotel
from app.models.room import Room
from app.models.booking import Booking
from app.models.inventory import Inventory
from app.models.user import User
from app.schemas.hotel import HotelSchema, HotelPriceOut, HotelInfoOut
from app.schemas.booking import HotelSearchRequest, HotelReportOut
from app.schemas.common import PageResponse
from app.database import get_by_id, get_all, create_record, update_record, delete_record


def _check_hotel_ownership(hotel: Hotel, current_user: User):
    """Reusable ownership guard — call this before any admin write on a hotel."""
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")


def create_hotel(db: Session, data: HotelSchema, current_user: User) -> Hotel:
    return create_record(
        db, Hotel,
        name=data.name,
        city=data.city,
        photos=data.photos,
        amenities=data.amenities,
        active=False,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        contact_address=data.contact_address,
        contact_location=data.contact_location,
        owner_id=current_user.id,
    )


def get_my_hotels(db: Session, current_user: User):
    # TODO: return get_all(db, Hotel, owner_id=current_user.id)
    pass


def get_hotel(db: Session, hotel_id: int, current_user: User) -> Hotel:
    # TODO:
    #   hotel = get_by_id(db, Hotel, hotel_id) → 404 if not found
    #   _check_hotel_ownership(hotel, current_user)
    #   return hotel
    pass


def update_hotel(db: Session, hotel_id: int, data: HotelSchema, current_user: User) -> Hotel:
    # TODO: fetch → check ownership → update_record(db, hotel, **data.model_dump(exclude_none=True, exclude={"id"}))
    pass


def activate_hotel(db: Session, hotel_id: int, current_user: User) -> Hotel:
    # TODO: fetch → check ownership → update_record(db, hotel, active=True)
    pass


def delete_hotel(db: Session, hotel_id: int, current_user: User) -> None:
    # TODO: fetch → check ownership → delete_record(db, hotel)
    pass


def get_hotel_bookings(db: Session, hotel_id: int, current_user: User):
    # TODO: fetch hotel → check ownership → get_all(db, Booking, hotel_id=hotel_id)
    pass


def get_report(db: Session, hotel_id: int, current_user: User,
               start_date: date = None, end_date: date = None) -> HotelReportOut:
    # TODO:
    #   Default start_date = today - 30 days, end_date = today
    #   Query Booking where hotel_id=hotel_id, status=CONFIRMED, check_in_date BETWEEN dates
    #   Compute: count, sum(amount), avg(amount)
    #   Return HotelReportOut(total_confirmed_bookings=..., total_revenue=..., avg_revenue=...)
    pass


def get_hotel_info(db: Session, hotel_id: int) -> HotelInfoOut:
    # TODO:
    #   hotel = get_by_id(db, Hotel, hotel_id) → 404 if not found or not active
    #   rooms = get_all(db, Room, hotel_id=hotel_id)
    #   return HotelInfoOut(hotel=HotelSchema.model_validate(hotel), rooms=[RoomSchema.model_validate(r) for r in rooms])
    pass


def search_hotels(db: Session, data: HotelSearchRequest) -> PageResponse:
    # TODO: Implement the GROUP BY + HAVING search query
    # See architecture §10 for the full SQL pattern using SQLAlchemy func.min and func.count
    pass
