from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.hotel import HotelSchema
from app.schemas.booking import HotelReportOut
from app.security.guards import require_hotel_manager
from app.services import hotel_service
from datetime import date

# dependencies=[...] applies require_hotel_manager to EVERY route in this router automatically.
# But we still Depends(require_hotel_manager) on individual routes to get the User object.
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
    """
    REFERENCE — Study this route before implementing the ones below.

    Pattern:
      1. Call the service function (service does ALL the logic)
      2. Convert the returned ORM object to a Pydantic schema with model_validate()
      3. Return it (FastAPI serializes via response_model)

    Notice: require_hotel_manager is used here (not get_current_user) because
    this router requires the HOTEL_MANAGER role. It still returns a User object.
    """
    hotel = hotel_service.create_hotel(db, data, current_user)
    return HotelSchema.model_validate(hotel)


@router.get("", response_model=list[HotelSchema])
def list_my_hotels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    GET /admin/hotels — list all hotels owned by this manager.

    The service returns a list of ORM Hotel objects.
    response_model=list[HotelSchema] tells FastAPI to serialize each one automatically.
    Do you need to call model_validate() manually, or does response_model handle it?

    Pattern: call service → return result.
    """
    return hotel_service.get_my_hotels(db, current_user)


@router.get("/{hotel_id}", response_model=HotelSchema)
def get_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    GET /admin/hotels/{hotel_id}

    The hotel_id path parameter is extracted from the URL automatically.
    Service handles: 404 if not found, 403 if not owner.

    Pattern: call service → return result.
    """
    return hotel_service.get_hotel(db, hotel_id, current_user)


@router.put("/{hotel_id}", response_model=HotelSchema)
def update_hotel(
    hotel_id: int,
    data: HotelSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    PUT /admin/hotels/{hotel_id} — full update of hotel details.

    Notice this is PUT (full replacement), not PATCH (partial).
    The service function signature takes: db, hotel_id, data, current_user.
    What are the four things you pass to the service?
    """
    return hotel_service.update_hotel(db, hotel_id, data, current_user)


@router.delete("/{hotel_id}", status_code=204)
def delete_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    DELETE /admin/hotels/{hotel_id} — status 204 No Content.

    After calling the service, what should you return for a 204 response?
    (Hint: think about what "No Content" means for the response body)
    """
    hotel_service.delete_hotel(db, hotel_id, current_user)
    return None



@router.patch("/{hotel_id}/activate", response_model=HotelSchema)
def activate_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    PATCH /admin/hotels/{hotel_id}/activate

    This endpoint only changes one thing: active → True.
    No request body is needed — the action is implied by the URL.
    PATCH is used here because it's a partial update (a single field).

    Pattern: call service → return result.
    """
    return hotel_service.activate_hotel(db, hotel_id, current_user)


@router.get("/{hotel_id}/bookings")
def hotel_bookings(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hotel_manager),
):
    """
    GET /admin/hotels/{hotel_id}/bookings

    Returns all bookings for a hotel the manager owns.
    No response_model is set — returns raw list from service.
    Pattern: call service → return result.
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
    """
    GET /admin/hotels/{hotel_id}/reports

    Returns aggregate revenue stats for a hotel.
    The date range (start_date, end_date) should be optional query parameters —
    look at the architecture spec §10 for the expected defaults.

    How do you declare optional query parameters in FastAPI?
    (Hint: they're just function arguments with default values — not path params, not body)

    Pattern: call hotel_service.get_report(...) with the right arguments → return result.
    """
    return hotel_service.get_report(db, hotel_id, current_user, start_date, end_date)
