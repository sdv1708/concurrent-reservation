# FastAPI AirBnb Backend — Complete Technical Specification

> **Purpose:** This document is the single source of truth for building a
> production-grade FastAPI backend that is an exact functional replica of the
> original Spring Boot AirBnb backend. It is written to be consumed by a
> developer or an AI agent building the system from scratch in a new repository.
> Do not deviate from these specifications without explicit instruction.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Tech Stack & Versions](#2-tech-stack--versions)
3. [Project Structure](#3-project-structure)
4. [Environment Configuration](#4-environment-configuration)
5. [Enums](#5-enums)
6. [Database Models](#6-database-models)
7. [Pydantic Schemas](#7-pydantic-schemas)
8. [Security Layer](#8-security-layer)
9. [Pricing Engine](#9-pricing-engine)
10. [API Endpoints — Full Reference](#10-api-endpoints--full-reference)
11. [Business Logic](#11-business-logic)
12. [Stripe Integration](#12-stripe-integration)
13. [Error Handling](#13-error-handling)
14. [Database Migrations](#14-database-migrations)
15. [Running the Application](#15-running-the-application)

---

## 1. System Overview

A RESTful hotel booking backend API with the following capabilities:

- **User authentication** via JWT (access + refresh token dual-token strategy)
- **Hotel & room management** for admin users (hotel managers)
- **Per-day inventory system** with availability tracking
- **Full booking lifecycle**: reserve → add guests → pay → confirm → cancel
- **Dynamic pricing engine** using the Decorator pattern (4 stacked multipliers)
- **Stripe Checkout** for hosted payment pages with webhook-based confirmation
- **Role-based access control**: `GUEST` and `HOTEL_MANAGER` roles

### Actor Summary

| Actor | Role | Access |
|---|---|---|
| Guest | `GUEST` | Browse hotels, create/manage own bookings, manage guests |
| Hotel Manager | `HOTEL_MANAGER` | CRUD hotels/rooms, manage inventory, view reports |
| Stripe | External | Calls `/webhook/payment` to confirm payments |

---

## 2. Tech Stack & Versions

```
fastapi==0.115.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9          # PostgreSQL driver
alembic==1.13.1                  # DB migrations
python-jose[cryptography]==3.3.0 # JWT
passlib[bcrypt]==1.7.4           # Password hashing
stripe==9.5.0                    # Stripe payments
pydantic[email]==2.7.0           # Schemas + validation
pydantic-settings==2.3.0        # Config from .env
python-dotenv==1.0.1
```

**Database:** PostgreSQL 15+
**Python:** 3.11+

---

## 3. Project Structure

```
airbnb-fastapi/
├── app/
│   ├── __init__.py
│   ├── main.py                    # App factory, router registration
│   ├── config.py                  # Settings (reads from .env)
│   ├── database.py                # SQLAlchemy engine + session + Base
│   ├── dependencies.py            # Shared Depends: get_db, get_current_user
│   │
│   ├── models/
│   │   ├── __init__.py            # re-exports all models
│   │   ├── enums.py               # All Enum types
│   │   ├── user.py                # User, UserRole
│   │   ├── hotel.py               # Hotel
│   │   ├── room.py                # Room
│   │   ├── inventory.py           # Inventory
│   │   ├── booking.py             # Booking, booking_guest join table
│   │   └── guest.py               # Guest
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                # SignUpRequest, LoginRequest, LoginResponse
│   │   ├── user.py                # UserOut, ProfileUpdateRequest
│   │   ├── hotel.py               # HotelSchema, HotelInfoOut, HotelPriceOut
│   │   ├── room.py                # RoomSchema
│   │   ├── inventory.py           # InventorySchema, UpdateInventoryRequest
│   │   ├── booking.py             # BookingRequest, BookingOut, ...
│   │   ├── guest.py               # GuestSchema
│   │   └── common.py              # PageResponse[T], ApiResponse[T]
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                # /auth
│   │   ├── users.py               # /users
│   │   ├── hotels_admin.py        # /admin/hotels
│   │   ├── rooms_admin.py         # /admin/hotels/{hotel_id}/rooms
│   │   ├── inventory_admin.py     # /admin/inventory
│   │   ├── hotels_browse.py       # /hotels (public)
│   │   ├── bookings.py            # /bookings
│   │   └── webhooks.py            # /webhook
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── hotel_service.py
│   │   ├── room_service.py
│   │   ├── inventory_service.py
│   │   ├── booking_service.py
│   │   ├── guest_service.py
│   │   └── user_service.py
│   │
│   ├── security/
│   │   ├── jwt.py                 # Token create + decode
│   │   └── guards.py              # get_current_user, require_role
│   │
│   ├── pricing/
│   │   ├── strategy.py            # Abstract base class
│   │   ├── base.py
│   │   ├── surge.py
│   │   ├── occupancy.py
│   │   ├── urgency.py
│   │   ├── holiday.py
│   │   └── pricing_service.py     # build chain + calculate
│   │
│   └── exceptions/
│       ├── custom.py              # ResourceNotFoundError, UnauthorizedError etc.
│       └── handlers.py            # @app.exception_handler registrations
│
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── .env
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 4. Environment Configuration

### `app/config.py`

```python
from pydantic_settings import BaseSettings
from datetime import timedelta

class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10      # 10 minutes (matches original)
    refresh_token_expire_days: int = 180        # 6 months (matches original)
    stripe_secret_key: str
    stripe_webhook_secret: str
    frontend_url: str

    class Config:
        env_file = ".env"

settings = Settings()
```

### `.env.example`

```env
DATABASE_URL=postgresql://airbnb_user:password@localhost:5432/airbnb
JWT_SECRET_KEY=your-secret-key-minimum-32-characters-long
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
FRONTEND_URL=http://localhost:3000
```

---

## 5. Enums

### `app/models/enums.py`

```python
from enum import Enum

class RoleEnum(str, Enum):
    GUEST         = "GUEST"
    HOTEL_MANAGER = "HOTEL_MANAGER"
    ADMIN         = "ADMIN"

class GenderEnum(str, Enum):
    MALE   = "MALE"
    FEMALE = "FEMALE"
    OTHER  = "OTHER"

class BookingStatusEnum(str, Enum):
    RESERVED         = "RESERVED"          # inventory held, payment not started
    GUESTS_ADDED     = "GUESTS_ADDED"      # guest list attached
    PAYMENTS_PENDING = "PAYMENTS_PENDING"  # Stripe session created
    CONFIRMED        = "CONFIRMED"         # Stripe webhook received
    CANCELLED        = "CANCELLED"         # cancelled + refunded

class PaymentStatusEnum(str, Enum):
    PENDING   = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
```

---

## 6. Database Models

### `app/database.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

---

### `app/models/user.py`

```python
from sqlalchemy import Column, BigInteger, String, Date, Enum as PgEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import GenderEnum

class User(Base):
    __tablename__ = "app_user"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name          = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender        = Column(PgEnum(GenderEnum), nullable=True)

    # Relationships
    roles    = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    hotels   = relationship("Hotel",   back_populates="owner")
    bookings = relationship("Booking", back_populates="user")
    guests   = relationship("Guest",   back_populates="user")


class UserRole(Base):
    """Separate join table — allows multi-role users."""
    __tablename__ = "user_roles"

    user_id = Column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
    role    = Column(String(50),                            primary_key=True)
    user    = relationship("User", back_populates="roles")
```

---

### `app/models/hotel.py`

```python
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Hotel(Base):
    __tablename__ = "Hotel"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    name            = Column(String, nullable=False)
    city            = Column(String, nullable=False)
    photos          = Column(ARRAY(TEXT), nullable=True)
    amenities       = Column(ARRAY(TEXT), nullable=True)
    active          = Column(Boolean, nullable=False, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Embedded contact info (flattened from Spring @Embedded HotelContactInfo)
    contact_phone   = Column(String, nullable=True)
    contact_email   = Column(String, nullable=True)
    contact_address = Column(String, nullable=True)
    contact_location= Column(String, nullable=True)  # "lat,lng" format

    owner_id   = Column(BigInteger, ForeignKey("app_user.id"), nullable=False)

    # Relationships
    owner       = relationship("User",      back_populates="hotels")
    rooms       = relationship("Room",      back_populates="hotel", cascade="all, delete-orphan")
    inventories = relationship("Inventory", back_populates="hotel")
    bookings    = relationship("Booking",   back_populates="hotel")
```

---

### `app/models/room.py`

```python
from sqlalchemy import Column, BigInteger, String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Room(Base):
    __tablename__ = "Room"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    hotel_id    = Column(BigInteger, ForeignKey("Hotel.id"), nullable=False)
    type        = Column(String,  nullable=False)           # e.g. "DELUXE", "SUITE"
    base_price  = Column(Numeric(10, 2), nullable=False)
    photos      = Column(ARRAY(TEXT), nullable=True)
    amenities   = Column(ARRAY(TEXT), nullable=True)
    total_count = Column(Integer, nullable=False)           # total rooms of this type
    capacity    = Column(Integer, nullable=False)           # max guests per room
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hotel       = relationship("Hotel",     back_populates="rooms")
    inventories = relationship("Inventory", back_populates="room", cascade="all, delete-orphan")
```

---

### `app/models/guest.py`

```python
from sqlalchemy import Column, BigInteger, String, Integer, ForeignKey, Enum as PgEnum
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import GenderEnum

class Guest(Base):
    __tablename__ = "Guest"

    id      = Column(BigInteger, primary_key=True, autoincrement=True)
    name    = Column(String,  nullable=False)
    gender  = Column(PgEnum(GenderEnum), nullable=True)
    age     = Column(Integer, nullable=True)
    user_id = Column(BigInteger, ForeignKey("app_user.id"), nullable=False)

    user = relationship("User", back_populates="guests")
```

---

### `app/models/inventory.py`

```python
from sqlalchemy import (Column, BigInteger, Integer, Numeric, Date, DateTime,
                         Boolean, String, ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Inventory(Base):
    """
    One row per (hotel_id, room_id, date) combination.
    Pre-generated for 365 days when a room is created on an active hotel.

    Columns:
      total_count    — total rooms of this type (from Room.total_count)
      book_count     — rooms fully confirmed (payment received)
      reserved_count — rooms in temporary hold (10-min payment window)
      available      = total_count - book_count - reserved_count
      surge_factor   — admin-set multiplier (default 1.0)
      price          — base price copied from Room.base_price at creation
      closed         — admin can close a date (maintenance, holidays)
    """
    __tablename__ = "Inventory"
    __table_args__ = (
        UniqueConstraint("hotel_id", "room_id", "date",
                         name="unique_hotel_room_date"),
    )

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    hotel_id       = Column(BigInteger, ForeignKey("Hotel.id"), nullable=False)
    room_id        = Column(BigInteger, ForeignKey("Room.id"),  nullable=False)
    date           = Column(Date,    nullable=False)
    book_count     = Column(Integer, nullable=False, default=0)
    reserved_count = Column(Integer, nullable=False, default=0)
    total_count    = Column(Integer, nullable=False)
    surge_factor   = Column(Numeric(5, 2),  nullable=False, default=1)
    price          = Column(Numeric(10, 2), nullable=False)
    city           = Column(String,  nullable=False)
    closed         = Column(Boolean, nullable=False, default=False)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hotel = relationship("Hotel", back_populates="inventories")
    room  = relationship("Room",  back_populates="inventories")
```

---

### `app/models/booking.py`

```python
from sqlalchemy import (Column, BigInteger, Integer, Numeric, Date, DateTime,
                         String, ForeignKey, Table, Enum as PgEnum)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.enums import BookingStatusEnum

# Many-to-many: Booking ↔ Guest
booking_guest = Table(
    "booking_guest", Base.metadata,
    Column("booking_id", BigInteger, ForeignKey("Booking.id"), primary_key=True),
    Column("guest_id",   BigInteger, ForeignKey("Guest.id"),   primary_key=True),
)

class Booking(Base):
    __tablename__ = "Booking"

    id                 = Column(BigInteger, primary_key=True, autoincrement=True)
    hotel_id           = Column(BigInteger, ForeignKey("Hotel.id"),    nullable=False)
    room_id            = Column(BigInteger, ForeignKey("Room.id"),     nullable=False)
    user_id            = Column(BigInteger, ForeignKey("app_user.id"), nullable=False)
    rooms_count        = Column(Integer,    nullable=False)
    check_in_date      = Column(Date,       nullable=False)
    check_out_date     = Column(Date,       nullable=False)
    booking_status     = Column(PgEnum(BookingStatusEnum), nullable=False,
                                default=BookingStatusEnum.RESERVED)
    amount             = Column(Numeric(10, 2), nullable=False)
    payment_session_id = Column(String, unique=True, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hotel  = relationship("Hotel",  back_populates="bookings")
    room   = relationship("Room")
    user   = relationship("User",   back_populates="bookings")
    guests = relationship("Guest",  secondary=booking_guest)
```

---

## 7. Pydantic Schemas

### `app/schemas/auth.py`

```python
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
from app.models.enums import GenderEnum

class SignUpRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    date_of_birth: Optional[date] = None
    gender: Optional[GenderEnum] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

### `app/schemas/user.py`

```python
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
from app.models.enums import GenderEnum

class UserOut(BaseModel):
    id: int
    name: Optional[str]
    email: str
    gender: Optional[GenderEnum]
    date_of_birth: Optional[date]
    model_config = {"from_attributes": True}

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[GenderEnum] = None
```

### `app/schemas/hotel.py`

```python
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

class HotelSchema(BaseModel):
    id: Optional[int] = None
    name: str
    city: str
    photos: Optional[List[str]] = []
    amenities: Optional[List[str]] = []
    active: Optional[bool] = False
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_address: Optional[str] = None
    contact_location: Optional[str] = None
    model_config = {"from_attributes": True}

class HotelPriceOut(BaseModel):
    """Used in paginated search results."""
    id: int
    name: str
    city: str
    min_price: Decimal
    model_config = {"from_attributes": True}

class HotelInfoOut(BaseModel):
    """Full hotel info with rooms — used in /hotels/{id}/info."""
    hotel: HotelSchema
    rooms: List["RoomSchema"]
```

### `app/schemas/room.py`

```python
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

class RoomSchema(BaseModel):
    id: Optional[int] = None
    type: str
    base_price: Decimal
    photos: Optional[List[str]] = []
    amenities: Optional[List[str]] = []
    total_count: int
    capacity: int
    model_config = {"from_attributes": True}
```

### `app/schemas/guest.py`

```python
from pydantic import BaseModel
from typing import Optional
from app.models.enums import GenderEnum

class GuestSchema(BaseModel):
    id: Optional[int] = None
    name: str
    gender: Optional[GenderEnum] = None
    age: Optional[int] = None
    model_config = {"from_attributes": True}
```

### `app/schemas/inventory.py`

```python
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import date

class InventorySchema(BaseModel):
    id: int
    date: date
    total_count: int
    book_count: int
    reserved_count: int
    price: Decimal
    surge_factor: Decimal
    closed: bool
    model_config = {"from_attributes": True}

class UpdateInventoryRequest(BaseModel):
    start_date: date
    end_date: date
    closed: Optional[bool] = None
    surge_factor: Optional[Decimal] = None
```

### `app/schemas/booking.py`

```python
from pydantic import BaseModel, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import date
from app.models.enums import BookingStatusEnum
from app.schemas.guest import GuestSchema

class BookingRequest(BaseModel):
    hotel_id: int
    room_id: int
    check_in_date: date
    check_out_date: date
    rooms_count: int

    @model_validator(mode="after")
    def validate_dates(self):
        if self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be after check_in_date")
        return self

class BookingOut(BaseModel):
    id: int
    hotel_id: int
    room_id: int
    check_in_date: date
    check_out_date: date
    booking_status: BookingStatusEnum
    amount: Decimal
    rooms_count: int
    guests: List[GuestSchema] = []
    model_config = {"from_attributes": True}

class BookingStatusResponse(BaseModel):
    booking_status: BookingStatusEnum

class BookingPaymentInitResponse(BaseModel):
    payment_url: str

class HotelReportOut(BaseModel):
    total_confirmed_bookings: int
    total_revenue: Decimal
    avg_revenue: Decimal

class HotelSearchRequest(BaseModel):
    city: str
    start_date: date
    end_date: date
    rooms_count: int
    page: int = 0
    size: int = 10
```

### `app/schemas/common.py`

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional

T = TypeVar("T")

class PageResponse(BaseModel, Generic[T]):
    content: List[T]
    total_elements: int
    total_pages: int
    page: int
    size: int
```

---

## 8. Security Layer

### `app/security/jwt.py`

```python
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.config import settings

def create_access_token(user_id: int, email: str, roles: list[str]) -> str:
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
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
```

### `app/security/guards.py`

```python
from fastapi import Depends, HTTPException, Request, Cookie
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.user import User
from app.models.enums import RoleEnum
from app.security.jwt import decode_token

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Reads Bearer token from Authorization header.
    Raises 401 if missing, invalid, or expired.
    Raises 401 if user no longer exists in DB.
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
    """Raises 403 if user does not have HOTEL_MANAGER role."""
    roles = [r.role for r in current_user.roles]
    if RoleEnum.HOTEL_MANAGER.value not in roles:
        raise HTTPException(403, "Hotel manager role required")
    return current_user
```

### Password Hashing

```python
# app/security/passwords.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

---

## 9. Pricing Engine

**Pattern:** Decorator (each class wraps the previous one, calls it first, then applies its own multiplier if condition is met.)

### `app/pricing/strategy.py`

```python
from abc import ABC, abstractmethod
from decimal import Decimal

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, inventory) -> Decimal:
        ...
```

### `app/pricing/base.py`

```python
from decimal import Decimal
from app.pricing.strategy import PricingStrategy

class BasePricing(PricingStrategy):
    def calculate(self, inventory) -> Decimal:
        return inventory.price * inventory.surge_factor
```

### `app/pricing/surge.py`

```python
from decimal import Decimal
from app.pricing.strategy import PricingStrategy

class SurgePricing(PricingStrategy):
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        if inventory.surge_factor > Decimal("1"):
            price *= inventory.surge_factor
        return price
```

### `app/pricing/occupancy.py`

```python
from decimal import Decimal
from app.pricing.strategy import PricingStrategy

class OccupancyPricing(PricingStrategy):
    """Adds 20% when more than 80% of rooms are booked."""
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        if inventory.total_count > 0:
            occupancy = inventory.book_count / inventory.total_count
            if occupancy > 0.8:
                price *= Decimal("1.20")
        return price
```

### `app/pricing/urgency.py`

```python
from decimal import Decimal
from datetime import date
from app.pricing.strategy import PricingStrategy

class UrgencyPricing(PricingStrategy):
    """Adds 15% if check-in date is within 7 days."""
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        days_away = (inventory.date - date.today()).days
        if 0 <= days_away <= 7:
            price *= Decimal("1.15")
        return price
```

### `app/pricing/holiday.py`

```python
from decimal import Decimal
from app.pricing.strategy import PricingStrategy

class HolidayPricing(PricingStrategy):
    """Adds 25% on weekends (Saturday=5, Sunday=6)."""
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        if inventory.date.weekday() >= 5:
            price *= Decimal("1.25")
        return price
```

### `app/pricing/pricing_service.py`

```python
from decimal import Decimal
from typing import List
from app.pricing.base import BasePricing
from app.pricing.surge import SurgePricing
from app.pricing.occupancy import OccupancyPricing
from app.pricing.urgency import UrgencyPricing
from app.pricing.holiday import HolidayPricing

def build_pricing_chain():
    """Builds the stacked decorator chain. Order matches original Java implementation."""
    s = BasePricing()
    s = SurgePricing(s)
    s = OccupancyPricing(s)
    s = UrgencyPricing(s)
    s = HolidayPricing(s)
    return s

def calculate_dynamic_price(inventory) -> Decimal:
    return build_pricing_chain().calculate(inventory)

def calculate_total_price(inventories: List) -> Decimal:
    """Sums dynamic price across all inventory rows (all dates in booking)."""
    chain = build_pricing_chain()
    return sum(chain.calculate(inv) for inv in inventories) or Decimal("0")
```

---

## 10. API Endpoints — Full Reference

### Auth — `/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | None | Create new user account |
| POST | `/auth/login` | None | Login, returns access token + sets refresh cookie |
| POST | `/auth/refresh` | Cookie | Generate new access token using refresh cookie |

#### `POST /auth/signup`
- **Request body:** `SignUpRequest`
- **Response:** `UserOut` (201)
- **Logic:** Check email uniqueness → hash password → save User → assign `GUEST` role

#### `POST /auth/login`
- **Request body:** `LoginRequest`
- **Response:** `LoginResponse` (200) + `Set-Cookie: refreshToken=...; HttpOnly`
- **Logic:** Verify email+password → generate access token (10 min) + refresh token (180 days) → return access in body, refresh in httpOnly cookie

#### `POST /auth/refresh`
- **Cookie required:** `refreshToken`
- **Response:** `LoginResponse` (200)
- **Logic:** Decode refresh token → load user → generate new access token

---

### Users — `/users` *(requires Bearer token)*

| Method | Path | Description |
|---|---|---|
| GET | `/users/profile` | Get current user profile |
| PATCH | `/users/profile` | Update name/dob/gender |
| GET | `/users/myBookings` | List all bookings for current user |
| GET | `/users/guests` | List all saved guests |
| POST | `/users/guests` | Add a new guest |
| PUT | `/users/guests/{guest_id}` | Update a guest |
| DELETE | `/users/guests/{guest_id}` | Delete a guest |

---

### Hotel Admin — `/admin/hotels` *(requires HOTEL_MANAGER role)*

| Method | Path | Description |
|---|---|---|
| POST | `/admin/hotels` | Create a new hotel |
| GET | `/admin/hotels` | List all hotels owned by current user |
| GET | `/admin/hotels/{hotel_id}` | Get hotel by ID |
| PUT | `/admin/hotels/{hotel_id}` | Update hotel details |
| DELETE | `/admin/hotels/{hotel_id}` | Delete hotel |
| PATCH | `/admin/hotels/{hotel_id}/activate` | Set `active = True` |
| GET | `/admin/hotels/{hotel_id}/bookings` | All bookings for hotel |
| GET | `/admin/hotels/{hotel_id}/reports` | Revenue report (date range) |

#### `GET /admin/hotels/{hotel_id}/reports`
- **Query params:** `start_date` (default: 1 month ago), `end_date` (default: today)
- **Response:** `HotelReportOut` → `{total_confirmed_bookings, total_revenue, avg_revenue}`
- **Logic:** Filter bookings by hotel + date range → count CONFIRMED → sum amounts

---

### Room Admin — `/admin/hotels/{hotel_id}/rooms` *(requires HOTEL_MANAGER role)*

| Method | Path | Description |
|---|---|---|
| POST | `/admin/hotels/{hotel_id}/rooms` | Create room (triggers inventory init if hotel is active) |
| GET | `/admin/hotels/{hotel_id}/rooms` | List all rooms |
| GET | `/admin/hotels/{hotel_id}/rooms/{room_id}` | Get room by ID |
| PUT | `/admin/hotels/{hotel_id}/rooms/{room_id}` | Update room |
| DELETE | `/admin/hotels/{hotel_id}/rooms/{room_id}` | Delete room + all inventory |

#### Create Room — Inventory Initialization
When a room is created **and the hotel is already active**, immediately generate
365 inventory records (from today to today+1 year):
```
for each date in [today, today+365]:
    INSERT INTO Inventory (hotel_id, room_id, date, price=room.base_price,
                           total_count=room.total_count, surge_factor=1,
                           book_count=0, reserved_count=0, closed=False, city=hotel.city)
```
Use `bulk_save_objects` for performance (not 365 individual commits).

---

### Inventory Admin — `/admin/inventory` *(requires HOTEL_MANAGER role)*

| Method | Path | Description |
|---|---|---|
| GET | `/admin/inventory/rooms/{room_id}` | List all inventory for a room |
| PATCH | `/admin/inventory/rooms/{room_id}` | Bulk update surge_factor / closed for a date range |

#### `PATCH /admin/inventory/rooms/{room_id}`
- **Request body:** `UpdateInventoryRequest` → `{start_date, end_date, closed?, surge_factor?}`
- **Logic:** `SELECT FOR UPDATE` rows in date range → update `closed` and/or `surge_factor` → commit

---

### Hotel Browse — `/hotels` *(requires Bearer token)*

| Method | Path | Description |
|---|---|---|
| GET | `/hotels/search` | Paginated hotel search with min price |
| GET | `/hotels/{hotel_id}/info` | Hotel details + room list |

#### `GET /hotels/search`
- **Request body:** `HotelSearchRequest` → `{city, start_date, end_date, rooms_count, page, size}`
- **Response:** `PageResponse[HotelPriceOut]`
- **Logic:**
  1. Calculate `days = (end_date - start_date).days + 1`
  2. Query `Inventory` where:
     - `city == city`
     - `date BETWEEN start_date AND end_date`
     - `closed == False`
     - `(total_count - book_count - reserved_count) >= rooms_count`
  3. `GROUP BY hotel_id HAVING COUNT(*) >= days` (ensures availability for ALL days)
  4. `MIN(price)` per hotel for display
  5. Paginate with `offset / limit`

---

### Bookings — `/bookings` *(requires Bearer token)*

| Method | Path | Description |
|---|---|---|
| POST | `/bookings/init` | Initialize booking, hold inventory |
| POST | `/bookings/{booking_id}/addGuests` | Attach guests to booking |
| POST | `/bookings/{booking_id}/payments` | Create Stripe session, get payment URL |
| POST | `/bookings/{booking_id}/cancel` | Cancel + refund |
| GET | `/bookings/{booking_id}/status` | Check current booking status |

---

### Webhook — `/webhook` *(public — no auth)*

| Method | Path | Description |
|---|---|---|
| POST | `/webhook/payment` | Stripe webhook — confirm payment |

---

## 11. Business Logic

### 11.1 Booking State Machine

```
RESERVED ──(addGuests)──► GUESTS_ADDED ──(initiatePayment)──► PAYMENTS_PENDING
                                                                      │
                                                              (Stripe webhook)
                                                                      │
                                                                  CONFIRMED
                                                                      │
                                                                 (cancel)
                                                                      │
                                                                  CANCELLED
```

**State transition rules:**
- `addGuests` → only allowed from `RESERVED`
- `initiatePayment` → allowed from `RESERVED` or `GUESTS_ADDED`
- `cancel` → only allowed from `CONFIRMED`
- Any action → check `has_booking_expired()` first (except status check)

**Booking expiry check:**
```python
def has_booking_expired(booking: Booking) -> bool:
    """Booking expires 10 minutes after creation if payment not started."""
    return datetime.utcnow() > booking.created_at + timedelta(minutes=10)
```

### 11.2 `POST /bookings/init` — Full Logic

```
1. Load Hotel by hotel_id → 404 if not found
2. Load Room by room_id   → 404 if not found
3. Calculate days = (check_out_date - check_in_date).days + 1
4. SELECT FOR UPDATE on Inventory rows WHERE:
   - room_id = room.id
   - date BETWEEN check_in_date AND check_out_date
   - closed = False
   - (total_count - book_count - reserved_count) >= rooms_count
5. If len(locked_rows) != days → raise 400 "Room not available"
6. For each inventory row: reserved_count += rooms_count
7. price_for_one_room = calculate_total_price(locked_rows)   # pricing engine
8. total_price = price_for_one_room * rooms_count
9. INSERT Booking (status=RESERVED, amount=total_price)
10. COMMIT
11. Return BookingOut
```

### 11.3 `POST /bookings/{id}/cancel` — Full Logic

```
1. Load Booking → 404 if not found
2. Assert booking.user_id == current_user.id → 403 if not
3. Assert booking.status == CONFIRMED → 400 if not
4. Set booking.status = CANCELLED
5. SELECT FOR UPDATE inventory rows (same date range + room)
6. For each: book_count = max(0, book_count - rooms_count)
7. Retrieve Stripe Session by booking.payment_session_id
8. stripe.Refund.create(payment_intent=session.payment_intent)
9. COMMIT
```

### 11.4 Webhook `POST /webhook/payment` — Full Logic

```
1. Read raw request bytes (MUST be raw, not parsed JSON)
2. stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
   → raises 400 if signature invalid
3. If event.type == "checkout.session.completed":
   a. Extract session_id from event data
   b. Load Booking by payment_session_id → 404 if not found
   c. SET booking.status = CONFIRMED
   d. SELECT FOR UPDATE inventory rows
   e. For each: reserved_count = max(0, reserved_count - rooms_count)
             book_count += rooms_count
   f. COMMIT
```

### 11.5 Ownership Checks

Always verify the current user owns the resource before any write operation:

```python
# Booking ownership
if booking.user_id != current_user.id:
    raise HTTPException(403, "Booking does not belong to you")

# Hotel ownership (for admin operations)
if hotel.owner_id != current_user.id:
    raise HTTPException(403, "You are not the owner of this hotel")

# Room ownership (via hotel)
if room.hotel.owner_id != current_user.id:
    raise HTTPException(403, "You are not the owner of this room")
```

---

## 12. Stripe Integration

### Setup

```python
# app/config.py — included
import stripe
stripe.api_key = settings.stripe_secret_key
```

### Creating a Checkout Session

```python
session = stripe.checkout.Session.create(
    payment_method_types=["card"],
    line_items=[{
        "price_data": {
            "currency": "usd",
            "product_data": {"name": f"Hotel Booking #{booking.id}"},
            "unit_amount": int(booking.amount * 100),  # Stripe uses cents
        },
        "quantity": 1,
    }],
    mode="payment",
    success_url=f"{settings.frontend_url}/payments/{booking.id}/status",
    cancel_url=f"{settings.frontend_url}/payments/{booking.id}/status",
)
# Store session.id in booking.payment_session_id
# Return session.url to client
```

### Webhook — Raw Body Requirement

```python
@router.post("/webhook/payment", status_code=204)
async def capture_payment(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    payload = await request.body()   # MUST be raw bytes — Stripe signs raw body
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid Stripe signature")
    # ... process event
```

### Refund on Cancellation

```python
session = stripe.checkout.Session.retrieve(booking.payment_session_id)
stripe.Refund.create(payment_intent=session.payment_intent)
```

---

## 13. Error Handling

### Custom Exceptions — `app/exceptions/custom.py`

```python
class ResourceNotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message

class UnauthorizedError(Exception):
    def __init__(self, message: str):
        self.message = message

class AccessDeniedError(Exception):
    def __init__(self, message: str):
        self.message = message
```

### Handlers — `app/exceptions/handlers.py`

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from app.exceptions.custom import (ResourceNotFoundError,
                                    UnauthorizedError, AccessDeniedError)

async def not_found_handler(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(404, {"error": {"code": 404, "message": exc.message}})

async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(401, {"error": {"code": 401, "message": exc.message}})

async def access_denied_handler(request: Request, exc: AccessDeniedError):
    return JSONResponse(403, {"error": {"code": 403, "message": exc.message}})

async def generic_handler(request: Request, exc: Exception):
    return JSONResponse(500, {"error": {"code": 500, "message": str(exc)}})
```

### Registration in `app/main.py`

```python
app.add_exception_handler(ResourceNotFoundError, not_found_handler)
app.add_exception_handler(UnauthorizedError,     unauthorized_handler)
app.add_exception_handler(AccessDeniedError,     access_denied_handler)
app.add_exception_handler(Exception,             generic_handler)
```

**Error response shape (consistent across all errors):**
```json
{
  "error": {
    "code": 404,
    "message": "Hotel not found with id: 5"
  }
}
```

---

## 14. Database Migrations

### Set Up Alembic

```bash
alembic init alembic
```

Edit `alembic/env.py`:
```python
from app.database import Base
from app.models import *          # imports all models so Alembic sees them
from app.config import settings

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

### Commands

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "initial_schema"

# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## 15. Running the Application

### `app/main.py`

```python
from fastapi import FastAPI
from app.routers import (auth, users, hotels_admin, rooms_admin,
                          inventory_admin, hotels_browse, bookings, webhooks)
from app.exceptions.handlers import (not_found_handler, unauthorized_handler,
                                       access_denied_handler, generic_handler)
from app.exceptions.custom import (ResourceNotFoundError, UnauthorizedError,
                                    AccessDeniedError)

def create_app() -> FastAPI:
    app = FastAPI(
        title="AirBnb API",
        version="1.0.0",
        docs_url="/swagger-ui.html",
    )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(hotels_admin.router)
    app.include_router(rooms_admin.router)
    app.include_router(inventory_admin.router)
    app.include_router(hotels_browse.router)
    app.include_router(bookings.router)
    app.include_router(webhooks.router)

    app.add_exception_handler(ResourceNotFoundError, not_found_handler)
    app.add_exception_handler(UnauthorizedError,     unauthorized_handler)
    app.add_exception_handler(AccessDeniedError,     access_denied_handler)
    app.add_exception_handler(Exception,             generic_handler)

    return app

app = create_app()
```

### Start Commands

```bash
# Development (auto-reload on file change)
uvicorn app.main:app --reload --port 8080

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

### Swagger UI

```
http://localhost:8080/swagger-ui.html
```

---

## 16. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"]
```

---

## 17. Implementation Notes for Agents

> Follow these rules strictly when building from this specification:

1. **Never skip the `SELECT FOR UPDATE`** on inventory rows during booking init and cancellation. Without it, concurrent bookings will cause double-booking.

2. **Webhook endpoint must read raw bytes**, not `request.json()`. Stripe signs the raw payload.

3. **Roles are stored as rows** in `user_roles` table, not as a column on `app_user`. Always query `user.roles` (relationship) to get roles.

4. **Refresh token goes in an httpOnly cookie**. Access token goes in the JSON response body only.

5. **Inventory is pre-generated for 365 days** when a room is created on an active hotel. Use `bulk_save_objects` not a loop of individual commits.

6. **Pricing chain order matters**: Base → Surge → Occupancy → Urgency → Holiday. Do not change the order.

7. **All admin endpoints** (`/admin/**`) must have `dependencies=[Depends(require_hotel_manager)]` on the router, not per-route.

8. **Ownership checks are separate from role checks.** Being a HOTEL_MANAGER does not grant access to another manager's hotels.

9. **Booking expiry is 10 minutes** from `created_at`. Check before `addGuests` and `initiatePayment`. Do not check before `cancel` (only status matters for cancel).

10. **Use `Decimal`** (not `float`) for all monetary values to avoid floating-point errors.
