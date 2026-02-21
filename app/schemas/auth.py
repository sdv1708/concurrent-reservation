from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
from app.models.enums import GenderEnum


class SignUpRequest(BaseModel):
    """Request body for POST /auth/signup"""
    name: str
    email: EmailStr
    password: str
    date_of_birth: Optional[date] = None
    gender: Optional[GenderEnum] = None


class LoginRequest(BaseModel):
    """Request body for POST /auth/login"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Response body for login and refresh — access token ONLY (refresh goes in cookie)"""
    access_token: str
    token_type: str = "bearer"
