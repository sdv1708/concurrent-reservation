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
    """Bulk-generates a year of inventory rows for a newly created room.

    Builds all 365 `Inventory` objects in memory and inserts them in a single
    transaction via `bulk_create` rather than 365 round-trips. Price and
    total_count are copied from the room at creation time; city is
    denormalized from the hotel to keep inventory search queries index-only.

    Args:
        db (Session): The database session.
        hotel (Hotel): The parent hotel (must be active).
        room (Room): The newly created room.
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
    """Creates a new room under a hotel owned by the current user.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the parent hotel.
        data (RoomSchema): The room details.
        current_user (User): The authenticated manager creating the room.

    Returns:
        Room: The newly created room record.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
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

    # Inactive hotels have no inventory yet — it's generated later on activation.
    if hotel.active:
        _init_inventory(db, hotel, room)

    return room


def get_rooms(db: Session, hotel_id: int, current_user: User):
    """Retrieves all rooms for a hotel after verifying ownership.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel.
        current_user (User): The authenticated manager.

    Returns:
        list[Room]: A list of the hotel's rooms.

    Raises:
        HTTPException: If the hotel is not found (404) or not owned by the user (403).
    """
    hotel = get_by_id(db, Hotel, hotel_id)
    if not hotel:
        raise HTTPException(404, f"Hotel not found: {hotel_id}")
    if hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this hotel")
    return get_all(db, Room, hotel_id=hotel_id)


def get_room(db: Session, hotel_id: int, room_id: int, current_user: User) -> Room:
    """Fetches a single room, verifying it belongs to the hotel and is owned by the user.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the hotel the room is expected to belong to.
        room_id (int): The ID of the room.
        current_user (User): The authenticated manager.

    Returns:
        Room: The room record.

    Raises:
        HTTPException: If the room is not found or does not belong to the
                       given hotel (404), or the hotel is not owned by the user (403).
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
    """Performs a full update of a room's details.

    Note that updating base_price or total_count does not retroactively change
    existing inventory rows — those were fixed at room creation time.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the parent hotel.
        room_id (int): The ID of the room to update.
        data (RoomSchema): The updated room properties.
        current_user (User): The authenticated manager.

    Returns:
        Room: The updated room record.

    Raises:
        HTTPException: If the hotel is not found (404), not owned by the user (403),
                       or the room is not found (404).
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
    """Deletes a room and, via cascade, its associated inventory rows.

    Args:
        db (Session): The database session.
        hotel_id (int): The ID of the parent hotel.
        room_id (int): The ID of the room to delete.
        current_user (User): The authenticated manager.

    Raises:
        HTTPException: If the hotel is not found (404), not owned by the user (403),
                       or the room is not found (404).
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
