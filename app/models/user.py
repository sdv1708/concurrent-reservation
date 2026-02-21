# ── Reference model — every other model follows this exact structure ──────────
#
# Pattern:
#   1. Inherit from Base (from app.database)
#   2. Define __tablename__ as a string (must match what ForeignKeys in OTHER models reference)
#   3. Columns are class-level attributes using Column(...)
#   4. relationship() wires ORM navigation — it does NOT add a DB column
#   5. cascade="all, delete-orphan" means deleting a User also deletes all its UserRoles

from sqlalchemy import Column, BigInteger, String, Date, Enum as PgEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import GenderEnum


class User(Base):
    __tablename__ = "app_user"   # "user" is a reserved word in Postgres — use app_user

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name          = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender        = Column(PgEnum(GenderEnum, name="genderenum"), nullable=True)

    # Relationships — navigate from user.roles, user.hotels, etc.
    roles    = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    hotels   = relationship("Hotel",   back_populates="owner")
    bookings = relationship("Booking", back_populates="user")
    guests   = relationship("Guest",   back_populates="user")


class UserRole(Base):
    """
    One row per (user, role) pair. This allows multi-role accounts.
    Roles are NOT stored as a column on app_user — always query user.roles.
    """
    __tablename__ = "user_roles"

    user_id = Column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
    role    = Column(String(50),                            primary_key=True)
    user    = relationship("User", back_populates="roles")
