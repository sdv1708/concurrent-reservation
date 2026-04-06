from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.hotel import HotelSchema
from app.schemas.booking import HotelReportOut
from app.security.guards import require_hotel_manager
from app.services import hotel_service
from datetime import date

# Note: dependencies=[Depends(require_hotel_manager)] applies require_hotel_manager 
# to EVERY route in this router automatically. We still define it in routes to inject the User object.
router = APIRouter(
    prefix="/admin/hotels",
    tags=["Hotel Admin"],
    dependencies=[Depends(require_hotel_manager)],
)


@router.post("", response_model=HotelSchema, status_code=201)
def create_hotel(
    data: HotelSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Creates a new hotel profile.
    
    Args:
        data (HotelSchema): The hotel details.
        db (Session): The database session.
        current_user (User): The authenticated manager creating the hotel.

    Returns:
        HotelSchema: The created hotel record.
    """
    hotel = hotel_service.create_hotel(db, data, current_user)
    return HotelSchema.model_validate(hotel)


@router.get("", response_model=list[HotelSchema])
def list_my_hotels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Lists all hotels managed by the authenticated user.
    
    Args:
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        list[HotelSchema]: A list of hotels owned by the manager.
    """
    return hotel_service.get_my_hotels(db, current_user)


@router.get("/{hotel_id}", response_model=HotelSchema)
def get_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Retrieves details of a specific hotel owned by the manager.
    
    Args:
        hotel_id (int): The ID of the hotel.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        HotelSchema: The hotel details.
    """
    return hotel_service.get_hotel(db, hotel_id, current_user)


@router.put("/{hotel_id}", response_model=HotelSchema)
def update_hotel(
    hotel_id: int,
    data: HotelSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Updates the details of a specific hotel.
    
    Args:
        hotel_id (int): The ID of the hotel to update.
        data (HotelSchema): The updated hotel data.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        HotelSchema: The updated hotel record.
    """
    return hotel_service.update_hotel(db, hotel_id, data, current_user)


@router.delete("/{hotel_id}", status_code=204)
def delete_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Deletes a specific hotel and all of its associated data.
    
    Args:
        hotel_id (int): The ID of the hotel to delete.
        db (Session): The database session.
        current_user (User): The authenticated manager.
    """
    hotel_service.delete_hotel(db, hotel_id, current_user)
    return None



@router.patch("/{hotel_id}/activate", response_model=HotelSchema)
def activate_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Activates a hotel, making it publically bookable.
    
    Args:
        hotel_id (int): The ID of the hotel to activate.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        HotelSchema: The activated hotel record.
    """
    return hotel_service.activate_hotel(db, hotel_id, current_user)


@router.get("/{hotel_id}/bookings")
def hotel_bookings(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """Retrieves all bookings made at a specific hotel.
    
    Args:
        hotel_id (int): The ID of the hotel.
        db (Session): The database session.
        current_user (User): The authenticated manager.

    Returns:
        list[Booking]: A list of bookings at the hotel.
    """
    return hotel_service.get_hotel_bookings(db, hotel_id, current_user)


@router.get("/{hotel_id}/reports", response_model=HotelReportOut)
def hotel_report(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
    start_date: date = None,
    end_date: date = None,
):
    """Generates an aggregate revenue report for the hotel.
    
    Args:
        hotel_id (int): The ID of the hotel.
        db (Session): The database session.
        current_user (User): The authenticated manager.
        start_date (date, optional): Reporting period start date.
        end_date (date, optional): Reporting period end date.

    Returns:
        HotelReportOut: The aggregated analytics report.
    """
    return hotel_service.get_report(db, hotel_id, current_user, start_date, end_date)
