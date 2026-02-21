from sqlalchemy import Column, BigInteger, String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Room(Base):
    __tablename__ = "Room"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    hotel_id    = Column(BigInteger, ForeignKey("Hotel.id"), nullable=False)
    type        = Column(String,  nullable=False)            # e.g. "DELUXE", "SUITE", "STANDARD"
    base_price  = Column(Numeric(10, 2), nullable=False)     # use Decimal, never float for money
    photos      = Column(ARRAY(TEXT), nullable=True)
    amenities   = Column(ARRAY(TEXT), nullable=True)
    total_count = Column(Integer, nullable=False)            # total physical rooms of this type
    capacity    = Column(Integer, nullable=False)            # max guests allowed per room
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    hotel       = relationship("Hotel",     back_populates="rooms")
    inventories = relationship("Inventory", back_populates="room", cascade="all, delete-orphan")
