from pydantic import BaseModel, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import date
from app.models.enums import BookingStatusEnum
from app.schemas.guest import GuestSchema


class BookingRequest(BaseModel):
    """Request body for POST /bookings/init — initiates a reservation."""
    hotel_id: int
    room_id: int
    check_in_date: date
    check_out_date: date
    rooms_count: int

    @model_validator(mode="after")
    def validate_dates(self):
        """Pydantic v2 cross-field validator — runs after all fields are set."""
        if self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be after check_in_date")
        return self


class BookingOut(BaseModel):
    """What we return for any booking — includes its attached guests."""
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
    """Lightweight response for GET /bookings/{id}/status."""
    booking_status: BookingStatusEnum


class BookingPaymentInitResponse(BaseModel):
    """Response for POST /bookings/{id}/payments — url to redirect user to Stripe."""
    payment_url: str


class HotelReportOut(BaseModel):
    """Revenue report returned for GET /admin/hotels/{id}/reports."""
    total_confirmed_bookings: int
    total_revenue: Decimal
    avg_revenue: Decimal


class HotelSearchRequest(BaseModel):
    """Request body for GET /hotels/search."""
    city: str
    start_date: date
    end_date: date
    rooms_count: int
    page: int = 0
    size: int = 10
