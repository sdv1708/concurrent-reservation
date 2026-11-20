from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.room import Room
from app.models.user import User
from app.schemas.inventory import UpdateInventoryRequest
from app.services import stay_inventory
from app.services.stay_inventory import InventoryNight
from app.database import get_by_id


def _check_room_ownership(db: Session, room_id: int, current_user: User) -> None:
    """Validates that the room type exists and that the user owns its hotel.

    Raises:
        HTTPException: If the room is not found (404) or not owned by the user (403).
    """
    room = get_by_id(db, Room, room_id)
    if not room:
        raise HTTPException(404, f"Room not found: {room_id}")
    if room.hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this room")


def get_room_inventory(db: Session, room_id: int, current_user: User) -> list[InventoryNight]:
    """Retrieves all inventory records for a specific room, in date order.

    Args:
        db (Session): The database session.
        room_id (int): The ID of the room.
        current_user (User): The authenticated manager.

    Returns:
        list[InventoryNight]: The inventory rows of the room type.

    Raises:
        HTTPException: If the room is not found (404) or not owned by the user (403).
    """
    _check_room_ownership(db, room_id, current_user)
    return stay_inventory.list_nights(db, room_id)


def bulk_update(db: Session, room_id: int, data: UpdateInventoryRequest,
                current_user: User) -> list[InventoryNight]:
    """Closes or opens nights, and sets the surge factor, over a date range.

    Both start_date and end_date are included. Closing a night stops new
    holds only. Existing holds and booked rooms stay valid.

    Args:
        db (Session): The database session.
        room_id (int): The ID of the room.
        data (UpdateInventoryRequest): Contains the start date, end date, and fields to update.
        current_user (User): The authenticated manager.

    Returns:
        list[InventoryNight]: The updated inventory rows.

    Raises:
        HTTPException: If the room is not found (404) or not owned by the user (403).
    """
    _check_room_ownership(db, room_id, current_user)
    nights = stay_inventory.change_nights(
        db, room_id, data.start_date, data.end_date,
        closed=data.closed, surge_factor=data.surge_factor,
    )
    db.commit()
    return nights
