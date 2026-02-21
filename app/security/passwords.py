from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt. Store only the hash — never the plain text."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against the stored bcrypt hash. Returns True if match."""
    return pwd_context.verify(plain, hashed)
