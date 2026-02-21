from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException
from app.models.inventory import Inventory
from app.models.room import Room
from app.models.user import User
from app.schemas.inventory import UpdateInventoryRequest
from app.database import get_by_id, get_all


def get_room_inventory(db: Session, room_id: int, current_user: User):
    # TODO:
    #   room = get_by_id(db, Room, room_id) → 404 if not found
    #   Check room.hotel.owner_id == current_user.id → 403 if not
    #   return get_all(db, Inventory, room_id=room_id)
    pass


def bulk_update(db: Session, room_id: int, data: UpdateInventoryRequest, current_user: User):
    # TODO:
    #   room = get_by_id(db, Room, room_id) → 404 if not found
    #   Check ownership
    #
    #   SELECT FOR UPDATE to lock rows in the date range:
    #   rows = db.execute(
    #       select(Inventory)
    #       .where(
    #           Inventory.room_id == room_id,
    #           Inventory.date.between(data.start_date, data.end_date),
    #       )
    #       .with_for_update()
    #   ).scalars().all()
    #
    #   For each row:
    #     if data.closed is not None: row.closed = data.closed
    #     if data.surge_factor is not None: row.surge_factor = data.surge_factor
    #
    #   db.commit()
    #   return rows
    pass
