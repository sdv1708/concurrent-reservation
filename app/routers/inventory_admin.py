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
    # TODO: Call inventory_service.get_room_inventory(db, room_id, current_user)
    # Hint: get_all(db, Inventory, room_id=room_id) — check room → hotel ownership first
    pass


@router.patch("/rooms/{room_id}", response_model=list[InventorySchema])
def update_inventory(
    room_id: int,
    data: UpdateInventoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call inventory_service.bulk_update(db, room_id, data, current_user)
    #
    # IMPORTANT — must use SELECT FOR UPDATE here too:
    #   rows = db.execute(
    #       select(Inventory)
    #       .where(Inventory.room_id == room_id,
    #              Inventory.date.between(data.start_date, data.end_date))
    #       .with_for_update()
    #   ).scalars().all()
    #
    # Then for each row: apply data.closed and/or data.surge_factor if provided
    # Commit once at the end.
    pass
