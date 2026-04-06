from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.user import User, UserRole
from app.models.enums import RoleEnum
from app.schemas.auth import SignUpRequest, LoginRequest
from app.schemas.user import UserOut
from app.security.passwords import hash_password, verify_password
from app.security.jwt import create_access_token, create_refresh_token, decode_token
from app.database import create_record


def sign_up(db: Session, data: SignUpRequest) -> UserOut:
    """Registers a new user and assigns a default GUEST role.

    Args:
        db (Session): The database session.
        data (SignUpRequest): Registration credentials.

    Returns:
        UserOut: The newly created user details.

    Raises:
        HTTPException: If the email is already registered (409).
    """
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(409, "Email already registered")

    user = create_record(
        db, User,
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
    )
    # Assign default GUEST role
    create_record(db, UserRole, user_id=user.id, role=RoleEnum.GUEST.value)
    return UserOut.model_validate(user)


def login(db: Session, data: LoginRequest) -> tuple[str, str]:
    """Authenticates a user and generates access and refresh tokens.

    Args:
        db (Session): The database session.
        data (LoginRequest): The login credentials.

    Returns:
        tuple[str, str]: A tuple containing (access_token, refresh_token).

    Raises:
        HTTPException: If the credentials are invalid (401).
    """
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    roles = [r.role for r in user.roles]
    return (
        create_access_token(user.id, user.email, roles),
        create_refresh_token(user.id),
    )


def refresh_access(db: Session, refresh_token: str) -> str:
    """Generates a new access token using a valid refresh token.

    Args:
        db (Session): The database session.
        refresh_token (str): The refresh token issued during login.

    Returns:
        str: A newly generated access token.

    Raises:
        HTTPException: If the token is invalid or the user does not exist (401).
    """
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(401, "Invalid refresh token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(401, "User not found")
    roles = [r.role for r in user.roles]
    return create_access_token(user.id, user.email, roles)
