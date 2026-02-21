# ── Reference service — every other service follows this structure ─────────────
#
# Pattern:
#   1. Takes db: Session as first arg (always)
#   2. Takes a schema (input data) and/or an ORM user object (for auth context)
#   3. Raises HTTPException for validation failures
#   4. Calls CRUD helpers from database.py — no raw SQL here
#   5. Returns ORM instances or Pydantic models (caller decides which)

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
    # Assign default GUEST role — roles live in user_roles table, not on User
    create_record(db, UserRole, user_id=user.id, role=RoleEnum.GUEST.value)
    return UserOut.model_validate(user)


def login(db: Session, data: LoginRequest) -> tuple[str, str]:
    """Returns (access_token, refresh_token). Router sets refresh in cookie."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    roles = [r.role for r in user.roles]
    return (
        create_access_token(user.id, user.email, roles),
        create_refresh_token(user.id),
    )


def refresh_access(db: Session, refresh_token: str) -> str:
    """Decode the refresh token, load the user, return a fresh access token."""
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(401, "Invalid refresh token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(401, "User not found")
    roles = [r.role for r in user.roles]
    return create_access_token(user.id, user.email, roles)
