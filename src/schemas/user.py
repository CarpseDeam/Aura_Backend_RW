# src/schemas/user.py
"""Pydantic models for User data."""
from pydantic import BaseModel, ConfigDict

class UserBase(BaseModel):
    """Base schema for user properties."""
    email: str

class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str
    beta_key: str  # <-- NEW: Add the beta key field

class UserLogin(BaseModel):
    """Schema for user login."""
    email: str
    password: str

class User(UserBase):
    """Schema for representing a user in API responses."""
    id: int
    model_config = ConfigDict(from_attributes=True)