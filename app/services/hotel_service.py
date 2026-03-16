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
    """Reusable ownership guard — call this before any admin write on a hotel."""
    if not hotel: 
      raise HTTPException(404, "Hotel not found")
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")


def create_hotel(db: Session, data: HotelSchema, current_user: User) -> Hotel:
    """
    REFERENCE — Study this pattern before implementing the functions below.

    Key things to notice:
    - Every field from the schema is passed explicitly — no shortcuts
    - active=False is hardcoded: a hotel always starts inactive (manager must activate it later)
    - owner_id is set to current_user.id server-side, never trusted from the client
    - create_record handles the INSERT, commit, and refresh in one call
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
    """
    Return all hotels owned by this user.

    Think about: which column on Hotel identifies the owner?
    Which helper returns ALL rows that match a single filter condition?
    You don't need a 404 check here — returning an empty list is valid.
    """
    return get_all(db, Hotel, owner_id=current_user.id)


def get_hotel(db: Session, hotel_id: int, current_user: User) -> Hotel:
    """
    Fetch a single hotel by ID, verifying it belongs to this user.

    Step by step:
      1. Fetch the hotel by primary key. What happens if it doesn't exist?
      2. Call the ownership guard that's already defined above in this file.
         The guard raises 403 automatically if ownership fails.
      3. Return the hotel.

    Notice the private helper `_check_hotel_ownership` at the top of this file —
    use it instead of repeating the ownership check manually.
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    _check_hotel_ownership(hotel, current_user)
    return hotel  


def update_hotel(db: Session, hotel_id: int, data: HotelSchema, current_user: User) -> Hotel:
    """
    Update a hotel's details (full replacement — this is a PUT, not PATCH).

    Steps:
      1. Fetch the hotel — 404 if not found
      2. Check ownership
      3. Apply the update

    When updating, should you allow the client to change the hotel's `id` field?
    Think about which fields to exclude from the update payload.
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    return update_record(db, hotel, **data.model_dump(exclude={"id"}))


def activate_hotel(db: Session, hotel_id: int, current_user: User) -> Hotel:
    """
    Set a hotel's `active` flag to True.

    This is a deliberate single-field update — only `active` changes.
    After activation, newly created rooms will automatically generate inventory rows.

    Steps: fetch → check ownership → update just the one field.
    What happens if you try to activate a hotel you don't own?
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    return update_record(db, hotel, active=True)



def delete_hotel(db: Session, hotel_id: int, current_user: User) -> None:
    """
    Delete a hotel and all its children (rooms, inventory).

    SQLAlchemy cascade rules on the Hotel model will handle the children automatically —
    you don't need to manually delete rooms or inventory.

    Steps: fetch → check ownership → delete.
    What should you return from a function with return type None?
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    delete_record(db, hotel)


def get_hotel_bookings(db: Session, hotel_id: int, current_user: User):
    """
    Return all bookings for a hotel — but only if this user owns it.

    The manager needs to verify the hotel exists AND that they own it
    before they can see its bookings.

    Steps: fetch hotel → check ownership → fetch all bookings filtered by hotel_id.
    Which model links bookings back to a hotel? Which field?
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel: 
      raise HTTPException(status_code=404, detail="Hotel not found")
    _check_hotel_ownership(hotel, current_user)
    return get_all(db, Booking, hotel_id=hotel_id)


def get_report(db: Session, hotel_id: int, current_user: User,
               start_date: date = None, end_date: date = None) -> HotelReportOut:
    """
    Generate a revenue report for a hotel over a date range.

    Defaults (when not provided by caller):
      - end_date = today
      - start_date = 30 days before end_date

    Think about what query you need to write:
      - Filter Booking by hotel_id
      - Only include CONFIRMED bookings (why not RESERVED or CANCELLED?)
      - Filter by check_in_date between start_date and end_date
      - You need three aggregates: count of bookings, sum of amounts, average of amounts

    SQLAlchemy provides func.count(), func.sum(), func.avg() for aggregations.
    Look at the imports at the top of this file — `func` is already imported.

    Return a HotelReportOut schema instance with the computed values.
    What do you return if there are zero confirmed bookings in the range?
    select(func.count()).select_from(users)
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
    
    
    

# ─── Phase 9 — Public hotel browse ──────────────────────────────────────────


def get_hotel_info(db: Session, hotel_id: int) -> HotelInfoOut:
    """
    Return full hotel info (hotel + rooms) for the public browse view.

    Important: this endpoint is PUBLIC (no ownership check) but should only
    return ACTIVE hotels. What should you raise if the hotel is inactive?

    Steps:
      1. Fetch the hotel. If not found OR not active → 404
      2. Fetch all rooms belonging to this hotel
      3. Build and return a HotelInfoOut — it takes `hotel` (a HotelSchema)
         and `rooms` (a list of RoomSchema). How do you convert ORM objects to schemas?

    Notice there is no `current_user` parameter here — why?
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel or not hotel.active: 
      raise HTTPException(status_code=404, detail="Hotel not found or not active")
    rooms = get_all(db, Room, hotel_id=hotel_id)
    return HotelInfoOut(hotel=HotelSchema.model_validate(hotel),
                        rooms=[RoomSchema.model_validate(r) for r in rooms])
    

def search_hotels(db: Session, data: HotelSearchRequest) -> PageResponse:
    """
    Search for hotels with availability for the requested dates and room count.

    This is the most complex query in the app — read this carefully.

    What the query must do:
      1. Look at the Inventory table (not Hotel directly) per city + date range
      2. For each inventory row, check that:
           - It's not closed
           - Available rooms = total_count - book_count - reserved_count >= rooms_count
      3. A hotel is only a match if it has qualifying rows for EVERY day in the range
         (use HAVING COUNT(*) >= number_of_days to enforce this)
      4. Select the minimum price per hotel for display (use func.min)
      5. Join back to Hotel, filter active=True
      6. Paginate with offset/limit based on data.page and data.size

    Concepts to look up:
      - SQLAlchemy subquery() + join()
      - func.min(), func.count(), group_by(), having()

    The result should be a PageResponse[HotelPriceOut].
    How do you count total elements for pagination without fetching all rows?
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
    
    
