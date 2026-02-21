from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
from app.models.enums import GenderEnum


class UserOut(BaseModel):
    """
    What we send back when a user is returned from any endpoint.
    model_config from_attributes=True lets Pydantic read directly from an ORM User object.
    Never expose password_hash in any response schema.
    """
    id: int
    name: Optional[str]
    email: str
    gender: Optional[GenderEnum]
    date_of_birth: Optional[date]
    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    """
    Request body for PATCH /users/profile.
    All fields are Optional — only provided fields get updated (partial update).
    """
    name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[GenderEnum] = None
