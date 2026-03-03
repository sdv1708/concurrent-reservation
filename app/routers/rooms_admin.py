from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.room import RoomSchema
from app.security.guards import require_hotel_manager
from app.services import room_service

# Note: hotel_id is part of the prefix — FastAPI passes it to every route function automatically
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
    """
    POST /admin/hotels/{hotel_id}/rooms — status 201 Created.

    The service create_room() handles everything including the conditional
    inventory initialization (only if the hotel is already active).
    The router just calls the service and returns the result.

    Pattern: call service → return result.
    """
    return room_service.create_room(db, hotel_id, data, current_user)


@router.get("", response_model=list[RoomSchema])
def list_rooms(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    GET /admin/hotels/{hotel_id}/rooms — list all rooms for this hotel.

    Ownership is verified in the service layer.
    Pattern: call service → return result.
    """
    return room_service.get_rooms(db, hotel_id, current_user)


@router.get("/{room_id}", response_model=RoomSchema)
def get_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    GET /admin/hotels/{hotel_id}/rooms/{room_id}

    Both hotel_id and room_id come from the URL path.
    The service verifies ownership via the hotel, not directly the room.

    Pattern: call service → return result.
    """
    return room_service.get_room(db, hotel_id, room_id, current_user)


@router.put("/{room_id}", response_model=RoomSchema)
def update_room(
    hotel_id: int,
    room_id: int,
    data: RoomSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    PUT /admin/hotels/{hotel_id}/rooms/{room_id} — full update of room details.

    The service handles ownership check and the actual update.
    How many arguments does room_service.update_room() take? (Look at its signature)

    Pattern: call service → return result.
    """
    return room_service.update_room(db, hotel_id, room_id, data, current_user)


@router.delete("/{room_id}", status_code=204)
def delete_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    DELETE /admin/hotels/{hotel_id}/rooms/{room_id} — status 204 No Content.

    Deleting the room also deletes all its inventory rows automatically
    (cascade defined on the Room model's `inventories` relationship).
    The router doesn't need to handle this — the service and ORM take care of it.

    After calling the service, what do you return for a 204?
    """
    room_service.delete_room(db, hotel_id, room_id, current_user)
    return None
