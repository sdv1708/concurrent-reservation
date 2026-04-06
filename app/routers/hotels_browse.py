from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.hotel import HotelPriceOut, HotelInfoOut
from app.schemas.common import PageResponse
from app.schemas.booking import HotelSearchRequest
from app.security.guards import get_current_user
from app.services import hotel_service

# Public browse — uses get_current_user (not require_hotel_manager)
# Any authenticated user can browse hotels
router = APIRouter(prefix="/hotels", tags=["Hotel Browse"])


@router.get("/search", response_model=PageResponse[HotelPriceOut])
def search_hotels(
    data: HotelSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Searches for active hotels with availability for the given dates.
    
    Args:
        data (HotelSearchRequest): The search criteria including city, dates, and pagination.
        db (Session): The database session.
        current_user (User): The authenticated user making the search.

    Returns:
        PageResponse[HotelPriceOut]: A paginated list of available hotels and their prices.
    """
    return hotel_service.search_hotels(db, data)


@router.get("/{hotel_id}/info", response_model=HotelInfoOut)
def hotel_info(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full details of a specific active hotel.
    
    Args:
        hotel_id (int): The ID of the hotel.
        db (Session): The database session.
        current_user (User): The authenticated user requesting the info.

    Returns:
        HotelInfoOut: The hotel's details and associated rooms.
    """
    return hotel_service.get_hotel_info(db, hotel_id)