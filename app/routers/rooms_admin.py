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
    """Creates a new room type for a specific hotel.
    
    Args:
        hotel_id (int): The ID of the hotel.
        data (RoomSchema): The room details.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        RoomSchema: The created room record.
    """
    return room_service.create_room(db, hotel_id, data, current_user)


@router.get("", response_model=list[RoomSchema])
def list_rooms(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Lists all room types available at a specific hotel.
    
    Args:
        hotel_id (int): The ID of the hotel.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        list[RoomSchema]: A list of rooms associated with the hotel.
    """
    return room_service.get_rooms(db, hotel_id, current_user)


@router.get("/{room_id}", response_model=RoomSchema)
def get_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Retrieves details of a specific room type at a hotel.
    
    Args:
        hotel_id (int): The ID of the hotel.
        room_id (int): The ID of the room.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        RoomSchema: The room details.
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
    """Updates the details of a specific room type.
    
    Args:
        hotel_id (int): The ID of the hotel.
        room_id (int): The ID of the room.
        data (RoomSchema): The updated room data.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        RoomSchema: The updated room record.
    """
    return room_service.update_room(db, hotel_id, room_id, data, current_user)


@router.delete("/{room_id}", status_code=204)
def delete_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Deletes a specific room type and cascades the deletion to its inventory.
    
    Args:
        hotel_id (int): The ID of the hotel.
        room_id (int): The ID of the room.
        db (Session): The database session.
        current_user (User): The authenticated manager.
    """
    room_service.delete_room(db, hotel_id, room_id, current_user)
    return None
