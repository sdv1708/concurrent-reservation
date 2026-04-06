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
    """Registers a new user.
    
    Args:
        data (SignUpRequest): The user registration details.
        db (Session): The database session.

    Returns:
        UserOut: The created user profile.
    """
    return auth_service.sign_up(db, data)


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticates a user and issues JWT tokens.
    
    Returns the access token in the response body, and sets the refresh 
    token in an HTTP-only cookie.
    
    Args:
        data (LoginRequest): The login credentials.
        response (Response): The FastAPI response object for setting cookies.
        db (Session): The database session.
        
    Returns:
        LoginResponse: Contains the access token.
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
    """Issues a new access token using a valid refresh token cookie.
    
    Args:
        refreshToken (Optional[str]): The refresh token from the HTTP-only cookie.
        db (Session): The database session.
        
    Returns:
        LoginResponse: Contains the new access token.
    """
    if not refreshToken:
        from fastapi import HTTPException
        raise HTTPException(401, "No refresh token cookie")
    access = auth_service.refresh_access(db, refreshToken)
    return LoginResponse(access_token=access)
