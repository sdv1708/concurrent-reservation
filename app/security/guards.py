from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.enums import RoleEnum
from app.security.jwt import decode_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Reads Bearer token from Authorization header and returns the authenticated User.

    Use as a Depends in any route that requires a logged-in user:
        @router.get("/profile")
        def profile(current_user: User = Depends(get_current_user)):
            ...

    Raises 401 if: header missing, token invalid/expired, user deleted from DB.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    try:
        payload = decode_token(auth.split(" ", 1)[1])
    except ValueError as e:
        raise HTTPException(401, str(e))
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_hotel_manager(current_user: User = Depends(get_current_user)) -> User:
    """
    Guards that require HOTEL_MANAGER role. Compose on top of get_current_user.

    Use on an entire router (all routes protected):
        router = APIRouter(dependencies=[Depends(require_hotel_manager)])

    Use on a single route:
        @router.post("/hotels")
        def create(current_user: User = Depends(require_hotel_manager)):
            ...

    Raises 403 if authenticated user does not have the HOTEL_MANAGER role.
    """
    roles = [r.role for r in current_user.roles]
    if RoleEnum.HOTEL_MANAGER.value not in roles:
        raise HTTPException(403, "Hotel manager role required")
    return current_user
