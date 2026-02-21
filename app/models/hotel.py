from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Hotel(Base):
    __tablename__ = "Hotel"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    name            = Column(String, nullable=False)
    city            = Column(String, nullable=False)
    photos          = Column(ARRAY(TEXT), nullable=True)
    amenities       = Column(ARRAY(TEXT), nullable=True)
    active          = Column(Boolean, nullable=False, default=False)  # must be activated before guests can book
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    # Flattened from Spring @Embedded HotelContactInfo — no separate contact table
    contact_phone    = Column(String, nullable=True)
    contact_email    = Column(String, nullable=True)
    contact_address  = Column(String, nullable=True)
    contact_location = Column(String, nullable=True)   # stored as "lat,lng" string

    owner_id = Column(BigInteger, ForeignKey("app_user.id"), nullable=False)

    owner       = relationship("User",      back_populates="hotels")
    rooms       = relationship("Room",      back_populates="hotel", cascade="all, delete-orphan")
    inventories = relationship("Inventory", back_populates="hotel")
    bookings    = relationship("Booking",   back_populates="hotel")
