from app.schemas.room import RoomSchema
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from fastapi import HTTPException
from datetime import date, timedelta
from app.models.hotel import Hotel
from app.models.room import Room
from app.models.enums import BookingStatusEnum
from app.models.booking import Booking
from app.models.inventory import Inventory
from app.models.user import User
from app.schemas.hotel import HotelSchema, HotelPriceOut, HotelInfoOut
from app.schemas.booking import HotelSearchRequest, HotelReportOut
from app.schemas.common import PageResponse
from app.database import get_by_id, get_all, create_record, update_record, delete_record


def _check_hotel_ownership(hotel: Hotel, current_user: User):
    """Validates that the authenticated user owns the specified hotel.

    Args:
        hotel (Hotel): The hotel record to check.
        current_user (User): The authenticated user making the request.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    if not hotel: 
      raise HTTPException(404, "Hotel not found")
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")


def create_hotel(db: Session, data: HotelSchema, current_user: User) -> Hotel:
    """Creates a new hotel profile.
    
    Hotels are created in an inactive state by default and must be explicitly activated.

    Args:
        db (Session): The database session.
        data (HotelSchema): The hotel details.
        current_user (User): The authenticated manager creating the hotel.

    Returns:
        Hotel: The newly created hotel record.
    """
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
    """Retrieves all hotels owned by the authenticated manager.

    Args:
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        list[Hotel]: A list of the manager's hotels.
    """
    return get_all(db, Hotel, owner_id=current_user.id)


def get_hotel(db: Session, hotel_id: int, current_user: User) -> Hotel:
    """Retrieves a specific hotel after verifying ownership.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel.
        current_user (User): The authenticated manager.

    Returns:
        Hotel: The hotel record.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    _check_hotel_ownership(hotel, current_user)
    return hotel  


def update_hotel(db: Session, hotel_id: int, data: HotelSchema, current_user: User) -> Hotel:
    """Performs a full update of a hotel's details.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel to update.
        data (HotelSchema): The updated hotel properties.
        current_user (User): The authenticated manager.

    Returns:
        Hotel: The updated hotel record.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    return update_record(db, hotel, **data.model_dump(exclude={"id"}))


def activate_hotel(db: Session, hotel_id: int, current_user: User) -> Hotel:
    """Activates a hotel, making it accessible to the public.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel to activate.
        current_user (User): The authenticated manager.

    Returns:
        Hotel: The activated hotel record.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    return update_record(db, hotel, active=True)



def delete_hotel(db: Session, hotel_id: int, current_user: User) -> None:
    """Deletes a hotel and cascades the deletion to its associated rooms and inventory.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel to delete.
        current_user (User): The authenticated manager.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    delete_record(db, hotel)


def get_hotel_bookings(db: Session, hotel_id: int, current_user: User):
    """Retrieves all bookings across all rooms for a specific hotel.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel.
        current_user (User): The authenticated manager.

    Returns:
        list[Booking]: A list of bookings at the hotel.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    return get_all(db, Booking, hotel_id=hotel_id)


def get_report(db: Session, hotel_id: int, current_user: User,
               start_date: date = None, end_date: date = None) -> HotelReportOut:
    """Generates an aggregate revenue report for a specific hotel.

    Calculates the total number of confirmed bookings and revenue metrics
    within the specified date range.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel.
        current_user (User): The authenticated manager.
        start_date (date, optional): Reporting period start date (defaults to 30 days prior).
        end_date (date, optional): Reporting period end date (defaults to today).

    Returns:
        HotelReportOut: The aggregated revenue statistics.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)

    if start_date is None:
      start_date = date.today() - timedelta(days=30)
    if end_date is None:
      end_date = date.today()
      
    stmt = select(func.count(Booking.id), func.sum(Booking.amount), func.avg(Booking.amount)).select_from(Booking).where(
        Booking.hotel_id == hotel_id,
        Booking.booking_status == BookingStatusEnum.CONFIRMED,
        Booking.check_in_date >= start_date,
        Booking.check_in_date <= end_date,
    )
    result = db.execute(stmt).first()

    return HotelReportOut(
        total_confirmed_bookings=result[0],
        total_revenue=result[1],
        avg_revenue=result[2],
    )
    
    
    

def get_hotel_info(db: Session, hotel_id: int) -> HotelInfoOut:
    """Retrieves full, public details of a hotel, including its active rooms.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel.

    Returns:
        HotelInfoOut: The hotel and room details.

    Raises:
        HTTPException: If the hotel is not found or is currently inactive (404).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel or not hotel.active: 
      raise HTTPException(status_code=404, detail="Hotel not found or not active")
    rooms = get_all(db, Room, hotel_id=hotel_id)
    return HotelInfoOut(hotel=HotelSchema.model_validate(hotel),
                        rooms=[RoomSchema.model_validate(r) for r in rooms])
    

def search_hotels(db: Session, data: HotelSearchRequest) -> PageResponse:
    """Searches for active hotels with availability corresponding to the requested dates.

    Queries inventory iteratively to ensure full contiguous availability across 
    the date range and provides dynamic minimum pricing metadata.

    Args:
        db (Session): The database session.
        data (HotelSearchRequest): The search query parameters (dates, rooms padding, pagination).

    Returns:
        PageResponse: A paginated page containing `HotelPriceOut` objects.
    """
    inventory_subquery = (
        select(Inventory.hotel_id, func.min(Inventory.price).label("min_price"))
        .where(
            Inventory.date >= data.check_in_date,
            Inventory.date <= data.check_out_date,
            Inventory.closed == False,
            (Inventory.total_count - Inventory.book_count - Inventory.reserved_count) >= data.rooms_count
        )
        .group_by(Inventory.hotel_id)
        .having(func.count(Inventory.hotel_id) >= (data.check_out_date - data.check_in_date).days)
        .subquery()
    )

    query = (
        select(Hotel, inventory_subquery.c.min_price)
        .join(inventory_subquery, Hotel.id == inventory_subquery.c.hotel_id)
        .where(Hotel.active == True)
    )
    
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()

    results = db.execute(
      query.offset((data.page - 1) * data.size).limit(data.size)
    ).all()

    content = [
      HotelPriceOut(**HotelSchema.model_validate(hotel).model_dump(),
      min_price=min_price,
    ) for hotel, min_price in results]


    return PageResponse(
      content=content,
      total_elements=total,
      page=data.page,
      size=data.size,
    ) 
    
    
