from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserOut, ProfileUpdateRequest
from app.schemas.guest import GuestSchema
from app.security.guards import get_current_user
from app.services import user_service
import logging

router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger(__name__)

@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    """
    GET /users/profile

    The router's job is simple: delegate to the service layer and return its result.
    The `response_model=UserOut` declaration tells FastAPI to serialize the return value
    automatically — so you don't need to do the conversion here.

    Notice that `db` is NOT in the parameters — why might the profile endpoint
    not need a database session, unlike the others?

    Pattern: call the corresponding user_service function and return the result.
    """

    return user_service.get_profile(current_user)


@router.patch("/profile", response_model=UserOut)
def update_profile(
    data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    PATCH /users/profile

    This is a partial update — only fields included in the request body are changed.
    The service layer handles that logic; the router just passes everything through.

    Pattern: call user_service.update_profile(...) with the right arguments, return the result.
    What three things does this endpoint have available to pass to the service?
    """
    return user_service.update_guest()


@router.get("/myBookings")
def my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GET /users/myBookings

    Returns a list of all bookings for the current user.
    No response_model is set here — the router returns the raw list from the service.

    Pattern: call user_service.get_my_bookings(...) and return the result.
    """
    pass


@router.get("/guests", response_model=list[GuestSchema])
def list_guests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GET /users/guests

    Returns all guest profiles saved by this user.
    `response_model=list[GuestSchema]` means FastAPI will serialize each item in the list.

    Pattern: call user_service.get_guests(...) and return the result.
    """
    pass


@router.post("/guests", response_model=GuestSchema, status_code=201)
def add_guest(
    data: GuestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    POST /users/guests — status 201 Created

    Creates a new guest associated with the current user.
    The `status_code=201` on the decorator means FastAPI returns HTTP 201 automatically.
    Your job here is just to call the service and return the new guest object.

    Pattern: call user_service.add_guest(...) and return the result.
    """
    pass


@router.put("/guests/{guest_id}", response_model=GuestSchema)
def update_guest(
    guest_id: int,
    data: GuestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    PUT /users/guests/{guest_id}

    Updates a specific guest by ID. The `guest_id` is extracted from the URL path
    automatically by FastAPI because it matches the path parameter name.

    The service handles the ownership check and the update logic.
    Your job: call user_service.update_guest(...) with all four needed arguments.
    What are they? Look at the service function signature.
    """
    pass


@router.delete("/guests/{guest_id}", status_code=204)
def delete_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    DELETE /users/guests/{guest_id} — status 204 No Content

    Deletes a guest by ID. HTTP 204 means "success, nothing to return."
    Notice there's no response_model — a 204 response has no body.

    After calling the service, what should you explicitly return?
    (Hint: what does HTTP 204 mean about the response body?)
    """
    pass
