from sqlalchemy import (
    Column, BigInteger, Integer, Numeric, Date, DateTime,
    Boolean, String, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Inventory(Base):
    """
    One row per (hotel_id, room_id, date) combination.

    Pre-generated for 365 days when a room is created on an active hotel.
    This table drives both availability search and pricing.

    Key columns:
      total_count    — total rooms of this type (copied from Room.total_count)
      book_count     — rooms fully confirmed (Stripe payment received)
      reserved_count — rooms in temporary hold (10-min payment window)
      available      = total_count - book_count - reserved_count  (computed, not stored)
      surge_factor   — admin-set price multiplier (default 1.0)
      price          — base price copied from Room.base_price at inventory creation
      closed         — admin can close a specific date (maintenance, holiday)
    """
    __tablename__ = "Inventory"
    __table_args__ = (
        # Ensures no duplicate (hotel, room, date) combinations
        UniqueConstraint("hotel_id", "room_id", "date", name="unique_hotel_room_date"),
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
    city           = Column(String,  nullable=False)   # denormalized for fast city-based search
    closed         = Column(Boolean, nullable=False, default=False)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    hotel = relationship("Hotel", back_populates="inventories")
    room  = relationship("Room",  back_populates="inventories")
