from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import date


class InventorySchema(BaseModel):
    """What we send back when showing inventory for a room (admin view)."""
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
    """
    Request body for PATCH /admin/inventory/rooms/{room_id}.
    Admin can close a date range or set a surge multiplier (or both).
    Both fields are optional — only provided ones get applied.
    """
    start_date: date
    end_date: date
    closed: Optional[bool] = None
    surge_factor: Optional[Decimal] = None
