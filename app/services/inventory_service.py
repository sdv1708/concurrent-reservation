from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.schemas.inventory import UpdateInventoryRequest
from app.database import get_by_id, get_all

def get_room_inventory(db: Session, room_id: int, current_user: User):
    """Retrieves all inventory records for a specific room.

    Args:
        db (Session): The database session.
        room_id (int): The ID of the room.
        current_user (User): The authenticated manager.

    Returns:
        list[Inventory]: A list of inventory rows.

    Raises:
        HTTPException: If the room is not found (404) or not owned by the user (403).
    """
    room = get_by_id(db, Room, room_id)
    if not room:
        raise HTTPException(404, f"Room not found: {room_id}")
    if room.hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this room")
    return get_all(db, Inventory, room_id=room_id)


def bulk_update(db: Session, room_id: int, data: UpdateInventoryRequest, current_user: User):
    """Bulk updates inventory availability or pricing modifiers over a date range.

    Applies pessimistic locking (SELECT FOR UPDATE) to ensure data integrity during 
    concurrent updates.

    Args:
        db (Session): The database session.
        room_id (int): The ID of the room.
        data (UpdateInventoryRequest): Contains the start date, end date, and fields to update.
        current_user (User): The authenticated manager.

    Returns:
        list[Inventory]: The updated inventory rows.

    Raises:
        HTTPException: If the room is not found (404) or not owned by the user (403).
    """

    room = get_by_id(db, Room, room_id)
    if not room: 
      raise HTTPException(404, f"Room not found {room_id}")
    if room.hotel.owner_id != current_user.id:
      raise HTTPException(403, 'You do not own this room')

    rows = db.execute((
            select(Inventory)
            .where(
                Inventory.room_id == room_id,
                Inventory.date.between(data.start_date, data.end_date),
            )).with_for_update()).scalars().all()
    
    for row in rows: 
      if data.closed is not None: 
        row.closed = data.closed
      if data.surge_factor is not None: 
        row.surge_factor = data.surge_factor 
    
    db.commit()
    return rows

  
