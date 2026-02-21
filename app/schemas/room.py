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
