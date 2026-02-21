from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.room import RoomSchema
from app.security.guards import require_hotel_manager
from app.services import room_service

router = APIRouter(
    prefix="/admin/hotels/{hotel_id}/rooms",
    tags=["Room Admin"],
    dependencies=[Depends(require_hotel_manager)],
)


@router.post("", response_model=RoomSchema, status_code=201)
def create_room(
    hotel_id: int,
    data: RoomSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call room_service.create_room(db, hotel_id, data, current_user)
    # IMPORTANT: If hotel.active is True, also call _init_inventory(db, hotel, room)
    #            to generate 365 inventory rows. Use bulk_create — NOT a loop.
    pass


@router.get("", response_model=list[RoomSchema])
def list_rooms(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call room_service.get_rooms(db, hotel_id, current_user)
    # Hint: get_all(db, Room, hotel_id=hotel_id) — check hotel ownership first
    pass


@router.get("/{room_id}", response_model=RoomSchema)
def get_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call room_service.get_room(db, hotel_id, room_id, current_user)
    pass


@router.put("/{room_id}", response_model=RoomSchema)
def update_room(
    hotel_id: int,
    room_id: int,
    data: RoomSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call room_service.update_room(db, hotel_id, room_id, data, current_user)
    # Hint: fetch room → check hotel ownership → update_record(db, room, **data.model_dump(exclude_none=True))
    pass


@router.delete("/{room_id}", status_code=204)
def delete_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    # TODO: Call room_service.delete_room(db, hotel_id, room_id, current_user)
    # Note: Room has cascade="all, delete-orphan" on inventories — deleting room also removes inventory
    pass
