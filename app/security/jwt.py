from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.config import settings


def create_access_token(user_id: int, email: str, roles: list[str]) -> str:
    """
    Creates a short-lived (10 min) JWT sent in the response body.
    Payload includes user_id (sub), email, and roles list for role checks.
    """
    return jwt.encode(
        {
            "sub":   str(user_id),
            "email": email,
            "roles": roles,
            "exp":   datetime.now(timezone.utc) + timedelta(
                         minutes=settings.access_token_expire_minutes),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: int) -> str:
    """
    Creates a long-lived (180 day) JWT stored in an httpOnly cookie.
    Only contains user_id — used only to mint new access tokens.
    """
    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + timedelta(
                       days=settings.refresh_token_expire_days),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT. Raises ValueError if expired or tampered.
    The caller (guard) converts this ValueError into an HTTP 401.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
