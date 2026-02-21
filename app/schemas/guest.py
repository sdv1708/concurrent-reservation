from pydantic import BaseModel
from typing import Optional
from app.models.enums import GenderEnum


class GuestSchema(BaseModel):
    """Used for both creating guests and returning them in responses."""
    id: Optional[int] = None
    name: str
    gender: Optional[GenderEnum] = None
    age: Optional[int] = None
    model_config = {"from_attributes": True}
