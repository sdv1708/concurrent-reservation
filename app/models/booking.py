from sqlalchemy import (
    Column, BigInteger, Integer, Numeric, Date, DateTime,
    String, ForeignKey, Table, Enum as PgEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
from app.models.enums import BookingStatusEnum


# ── Association table — many-to-many between Booking and Guest ───────────────
# This is a plain Table, NOT a model class. SQLAlchemy handles it automatically.
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
    rooms_count        = Column(Integer,    nullable=False)            # number of rooms booked
    check_in_date      = Column(Date,       nullable=False)
    check_out_date     = Column(Date,       nullable=False)
    booking_status     = Column(
        PgEnum(BookingStatusEnum, name="bookingstatusenum"),
        nullable=False,
        default=BookingStatusEnum.RESERVED,
    )
    amount             = Column(Numeric(10, 2), nullable=False)         # total price calculated at init
    payment_session_id = Column(String, unique=True, nullable=True)     # Stripe checkout session ID
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                                onupdate=lambda: datetime.now(timezone.utc))

    hotel  = relationship("Hotel",  back_populates="bookings")
    room   = relationship("Room")
    user   = relationship("User",   back_populates="bookings")
    guests = relationship("Guest",  secondary=booking_guest)   # via association table
