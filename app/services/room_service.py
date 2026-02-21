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

    Uses bulk_create (single commit, not 365 individual commits).
    This is the correct pattern for any large batch insert.
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
    # TODO:
    #   hotel = get_by_id(db, Hotel, hotel_id) → 404 if not found
    #   check hotel.owner_id == current_user.id → 403 if not
    #   return get_all(db, Room, hotel_id=hotel_id)
    pass


def get_room(db: Session, hotel_id: int, room_id: int, current_user: User) -> Room:
    # TODO: fetch room → verify room.hotel.owner_id == current_user.id → return room
    pass


def update_room(db: Session, hotel_id: int, room_id: int, data: RoomSchema, current_user: User) -> Room:
    # TODO: fetch room → check ownership → update_record(db, room, **data.model_dump(exclude_none=True, exclude={"id"}))
    pass


def delete_room(db: Session, hotel_id: int, room_id: int, current_user: User) -> None:
    # TODO: fetch room → check ownership → delete_record(db, room)
    # Note: cascade on Room.inventories means all Inventory rows are also deleted automatically
    pass
