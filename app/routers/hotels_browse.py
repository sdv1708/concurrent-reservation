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
    """
    GET /hotels/search

    Searches for hotels with availability across all requested dates.
    The request body (`HotelSearchRequest`) contains: city, start_date, end_date,
    rooms_count, page, and size.

    The service does the heavy SQL work — the router just passes the request through
    and returns a PageResponse[HotelPriceOut].

    Note on the response type: PageResponse is a generic, and the router declares
    exactly what type each item in `content` should be (HotelPriceOut).

    Pattern: call service → return result.
    """
    return hotel_service.search_hotels(db, data)


@router.get("/{hotel_id}/info", response_model=HotelInfoOut)
def hotel_info(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GET /hotels/{hotel_id}/info

    Returns full hotel details (hotel + list of rooms) for the public detail view.
    This route is accessible by any authenticated user, not just managers.
    The service verifies the hotel is active before returning.

    response_model=HotelInfoOut — what two fields does that schema contain?

    Pattern: call service → return result.
    """
    return hotel_service.get_hotel_info(db, hotel_id)