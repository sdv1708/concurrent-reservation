# ── Reference schema file — use this pattern for every schema you write ──────
#
# Key rules:
#   - "Request" schemas: used for incoming data (POST/PUT body), may have required fields
#   - "Out" schemas: used for outgoing data (responses), always have from_attributes=True
#   - Optional fields with = None mean the client doesn't have to send them
#   - from_attributes=True enables: HotelSchema.model_validate(hotel_orm_object)

from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal


class HotelSchema(BaseModel):
    """Used for both create/update requests AND hotel responses."""
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
    """
    Minimal hotel info returned in paginated search results.
    min_price is computed in the search query — not a column on Hotel.
    This is a raw query result shape, not an ORM object, so no from_attributes needed
    for the price field, but keep it for consistency.
    """
    id: int
    name: str
    city: str
    min_price: Decimal
    model_config = {"from_attributes": True}


class HotelInfoOut(BaseModel):
    """Full hotel details + its rooms — returned from GET /hotels/{id}/info"""
    hotel: HotelSchema
    rooms: List["RoomSchema"]


# Resolve forward reference after RoomSchema is defined
from app.schemas.room import RoomSchema  # noqa — must be after class definition
HotelInfoOut.model_rebuild()
