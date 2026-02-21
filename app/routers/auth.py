# ── Reference router — use this file as the template for every router you write ──
#
# Pattern:
#   1. Create an APIRouter with prefix and tags
#   2. Routes are THIN: extract request data, call the service, return the schema
#   3. All business logic lives in the service — NOT in the router
#   4. Use Depends(get_db) for DB session, Depends(get_current_user) for auth

from fastapi import APIRouter, Depends, Response, Cookie
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.schemas.auth import SignUpRequest, LoginRequest, LoginResponse
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(data: SignUpRequest, db: Session = Depends(get_db)):
    """
    Register a new user.
    Checks email uniqueness → hashes password → creates User + GUEST role.
    Returns the created user (without password_hash).
    """
    return auth_service.sign_up(db, data)


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Authenticate user.
    Returns access token in response body.
    Sets refresh token in an httpOnly cookie (invisible to JavaScript).
    """
    access, refresh = auth_service.login(db, data)
    response.set_cookie(
        key="refreshToken",
        value=refresh,
        httponly=True,      # JavaScript cannot read this — XSS protection
        samesite="lax",
        max_age=60 * 60 * 24 * 180,
    )
    return LoginResponse(access_token=access)


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    refreshToken: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
):
    """
    Use the refresh cookie to mint a new access token.
    Client calls this when their 10-minute access token expires.
    """
    if not refreshToken:
        from fastapi import HTTPException
        raise HTTPException(401, "No refresh token cookie")
    access = auth_service.refresh_access(db, refreshToken)
    return LoginResponse(access_token=access)
