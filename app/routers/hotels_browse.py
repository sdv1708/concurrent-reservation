from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.hotel import HotelPriceOut, HotelInfoOut
from app.schemas.common import PageResponse
from app.schemas.booking import HotelSearchRequest
from app.security.guards import get_current_user
from app.services import hotel_service

router = APIRouter(prefix="/hotels", tags=["Hotel Browse"])


@router.get("/search", response_model=PageResponse[HotelPriceOut])
def search_hotels(
    data: HotelSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call hotel_service.search_hotels(db, data)
    #
    # Query pattern (all in one SQLAlchemy query):
    #   GROUP BY hotel_id on Inventory table
    #   WHERE city=data.city, date BETWEEN ..., closed=False,
    #         (total_count - book_count - reserved_count) >= data.rooms_count
    #   HAVING COUNT(*) >= (end_date - start_date).days + 1  ← availability on ALL days
    #   SELECT MIN(price) per hotel for display
    #   Then paginate with offset/limit
    pass


@router.get("/{hotel_id}/info", response_model=HotelInfoOut)
def hotel_info(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: Call hotel_service.get_hotel_info(db, hotel_id)
    # Hint: fetch Hotel → fetch its rooms → return HotelInfoOut(hotel=..., rooms=[...])
    pass
