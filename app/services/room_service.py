from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import date, timedelta
from app.models.room import Room
from app.models.hotel import Hotel
from app.models.inventory import Inventory
from app.models.user import User
from app.schemas.room import RoomSchema
from app.database import get_by_id, get_all, create_record, update_record, delete_record, bulk_create


def _init_inventory(db: Session, hotel: Hotel, room: Room) -> None:
    """
    REFERENCE — bulk generate 365 inventory rows when a room is created on an active hotel.

    Study this before implementing the functions below. Key things to notice:
      - A list comprehension builds all 365 Inventory objects in memory first
      - bulk_create() sends them in a single transaction (not 365 round-trips)
      - Each row copies price and total_count from the room at creation time
      - city is denormalized (copied from hotel) to make inventory queries faster
      - All counts start at 0; surge_factor starts at 1; closed starts as False
    """
    today = date.today()
    rows = [
        Inventory(
            hotel_id=hotel.id,
            room_id=room.id,
            date=today + timedelta(days=i),
            price=room.base_price,
            total_count=room.total_count,
            surge_factor=1,
            book_count=0,
            reserved_count=0,
            closed=False,
            city=hotel.city,
        )
        for i in range(365)
    ]
    bulk_create(db, rows)


def create_room(db: Session, hotel_id: int, data: RoomSchema, current_user: User) -> Room:
    """
    REFERENCE — Study this before implementing the functions below.

    The important decision here: inventory rows are only generated if the hotel
    is ALREADY active. If the hotel is inactive, inventory is created later when
    the hotel gets activated. Notice the conditional `if hotel.active` pattern.
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel:
        raise HTTPException(404, f"Hotel not found: {hotel_id}")
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")

    room = create_record(
        db, Room,
        hotel_id=hotel_id,
        type=data.type,
        base_price=data.base_price,
        photos=data.photos,
        amenities=data.amenities,
        total_count=data.total_count,
        capacity=data.capacity,
    )

    # Only init inventory if the hotel is already active
    if hotel.active:
        _init_inventory(db, hotel, room)

    return room


def get_rooms(db: Session, hotel_id: int, current_user: User):
    """
    Return all rooms for a hotel — only if this user owns the hotel.

    Notice the two-step verification:
      Step 1 — does the hotel even exist? (404 if not)
      Step 2 — does this user own it? (403 if not)

    Only after both checks pass should you fetch the rooms.
    Which field on Hotel links to the owner? Which field on Room links to the hotel?
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel:
        raise HTTPException(404, f"Hotel not found: {hotel_id}")
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")
    return get_all(db, Room, hotel_id=hotel_id)


def get_room(db: Session, hotel_id: int, room_id: int, current_user: User) -> Room:
    """
    Fetch a single room, verifying hotel ownership.

    Think about: how do you check ownership using a room object rather than a hotel object?
    The Room model has a relationship to Hotel — how do you traverse from `room` to its hotel's owner?

    Hint: look at what `room.hotel` gives you.
    """
    room = get_by_id(db, Room, room_id)
    if not room:
        raise HTTPException(404, f"Room not found: {room_id}")
        
    if room.hotel_id != hotel_id:
        raise HTTPException(404, f"Room {room_id} does not belong to hotel {hotel_id}")

    if room.hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this room")
    return room


def update_room(db: Session, hotel_id: int, room_id: int, data: RoomSchema, current_user: User) -> Room:
    """
    Update a room's details — only if the requesting user owns the parent hotel.

    Steps:
      1. Verify the hotel exists and is owned by current_user
      2. Verify the room exists
      3. Apply the update

    Should you allow the client to change the room's `id` field via the update?
    Think about what to exclude from the data dump.

    Note: updating base_price or total_count does NOT retroactively change
    existing inventory rows — those were set at room creation.
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel:
        raise HTTPException(404, f"Hotel not found: {hotel_id}")
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")
    room = get_by_id(db, Room, room_id)
    if not room:
        raise HTTPException(404, f"Room not found: {room_id}")
    return update_record(db, room, **data.model_dump(exclude_none=True, exclude={"id"}))

def delete_room(db: Session, hotel_id: int, room_id: int, current_user: User) -> None:
    """
    Delete a room — only if the requesting user owns the parent hotel.

    Something to understand: the Room model has `cascade="all, delete-orphan"`
    on its `inventories` relationship. What does that mean happens automatically
    when you delete the room?

    Steps: verify hotel ownership → fetch room → delete.
    You do NOT need to manually delete inventory rows — why?
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel:
        raise HTTPException(404, f"Hotel not found: {hotel_id}")
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")
    room = get_by_id(db, Room, room_id)
    if not room:
        raise HTTPException(404, f"Room not found: {room_id}")
    delete_record(db, room)
