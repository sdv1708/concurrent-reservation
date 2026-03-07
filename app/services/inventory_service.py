from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.schemas.inventory import UpdateInventoryRequest
from app.database import get_by_id, get_all


def get_room_inventory(db: Session, room_id: int, current_user: User):
    """
    Return all inventory rows for a room — only if this user owns the parent hotel.

    The ownership chain here is: Room → Hotel → owner_id.
    You need to traverse two levels to verify access.

    Think about: how do you get from a `room` object to its hotel's owner?
    (Hint: the Room model has a `hotel` relationship)

    After verifying ownership, return all inventory rows for this room.
    """
    room = get_by_id(db, Room, room_id)
    if not room:
        raise HTTPException(404, f"Room not found: {room_id}")
    if room.hotel.owner_id != current_user.id:
        raise HTTPException(403, "You do not own this room")
    return get_all(db, Inventory, room_id=room_id)


def bulk_update(db: Session, room_id: int, data: UpdateInventoryRequest, current_user: User):
    """
    Update closed/surge_factor for all inventory rows in a date range.

    This function introduces an important concept: SELECT FOR UPDATE (pessimistic locking).
    Why is it needed here? Imagine two admins updating the same inventory rows at the same time.
    Without a lock, one update could silently overwrite the other.

    The pattern to use:
      - Use db.execute(...) with a select() query (not get_all)
      - Add .with_for_update() to the query — this locks the matching rows
      - Call .scalars().all() to get the list of Inventory objects
      - Rows stay locked until the transaction is committed

    Steps to think through:
      1. Verify the room exists (404) and you own the hotel (403)
      2. Build the SELECT FOR UPDATE query filtering by room_id and date range
      3. Loop over the returned rows:
           - Only update `closed` if data.closed is not None
           - Only update `surge_factor` if data.surge_factor is not None
           (Why check for None? Because this is a partial update — not every field may be sent)
      4. Commit once at the end — NOT inside the loop
      5. Return the updated rows

    Look at the `select` import at the top — it's already imported.
    The date range filter uses: Inventory.date.between(data.start_date, data.end_date)
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
            )).with_for_update()).scalars().all() # pessimistic locking 
    
    for row in rows: 
      if data.closed is not None: 
        row.closed = data.closed
      if data.surge_factor is not None: 
        row.surge_factor = data.surge_factor() 
    
    db.commit()
    return rows

  
