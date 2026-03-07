from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.inventory import InventorySchema, UpdateInventoryRequest
from app.security.guards import require_hotel_manager
from app.services import inventory_service

router = APIRouter(
    prefix="/admin/inventory",
    tags=["Inventory Admin"],
    dependencies=[Depends(require_hotel_manager)],
)


@router.get("/rooms/{room_id}", response_model=list[InventorySchema])
def list_inventory(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    GET /admin/inventory/rooms/{room_id}

    Returns all 365 inventory rows for a room.
    The service handles verifying ownership (room → hotel → owner).

    Pattern: call service → return result.
    """
    return inventory_service.get_room_inventory(db, room_id, current_user)


@router.patch("/rooms/{room_id}", response_model=list[InventorySchema])
def update_inventory(
    room_id: int,
    data: UpdateInventoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    PATCH /admin/inventory/rooms/{room_id}

    Bulk-updates inventory rows in a date range (set closed and/or surge_factor).
    PATCH is appropriate here because only some fields may be updated.

    The service uses SELECT FOR UPDATE internally — you don't need to manage
    the locking here in the router; just pass the arguments through.

    Pattern: call inventory_service.bulk_update(...) → return the list of updated rows.
    """
    return inventory_service.bulk_update(db=db, room_id=room_id, data=data, current_user=current_user)
