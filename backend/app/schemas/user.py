"""User schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import PlanType


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    plan_type: PlanType
    tokens_used: int
    reviews_count: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: int  # user_id
    exp: datetime
    iat: datetime
