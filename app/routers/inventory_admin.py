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
    """Lists the 365-day inventory for a specific room.
    
    Args:
        room_id (int): The ID of the room.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        list[InventorySchema]: Ordered list of inventory rows for the room.
    """
    return inventory_service.get_room_inventory(db, room_id, current_user)


@router.patch("/rooms/{room_id}", response_model=list[InventorySchema])
def update_inventory(
    room_id: int,
    data: UpdateInventoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Bulk-updates inventory for a room over a specified date range.
    
    Can apply temporary closures or adjust dynamic pricing (surge factor).
    
    Args:
        room_id (int): The ID of the room.
        data (UpdateInventoryRequest): The update details (date range, closures, surge).
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        list[InventorySchema]: The updated inventory rows.
    """
    return inventory_service.bulk_update(db=db, room_id=room_id, data=data, current_user=current_user)
