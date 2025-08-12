"""Pydantic models for User data.

This module defines the Pydantic schemas for user-related data transfer objects (DTOs).
These schemas are used for request validation, response serialization, and interacting
with the database layer.
"""

from pydantic import BaseModel


class UserBase(BaseModel):
    """Base schema for user properties.

    This schema defines the common attributes shared across different user-related
    operations.

    Attributes:
        email: The user's unique email address.
    """
    email: str


class UserCreate(UserBase):
    """Schema for creating a new user.

    This schema is used for the user registration endpoint. It inherits the email
    from UserBase and adds a password field required for creating a new user account.

    Attributes:
        password: The user's chosen password.
    """
    password: str


class UserLogin(BaseModel):
    """Schema for user login.

    This schema is used for the authentication endpoint, requiring the user's
    credentials for verification.

    Attributes:
        email: The user's email address.
        password: The user's password.
    """
    email: str
    password: str


class User(UserBase):
    """Schema for representing a user in API responses.

    This schema is used when returning user data from the API. It includes the
    user's ID and inherits the email from UserBase. The password is intentionally
    excluded for security.

    Attributes:
        id: The unique integer identifier for the user.
    """
    id: int

    class Config:
        """Pydantic configuration options for the User schema.

        Enables ORM mode to allow the model to be created from SQLAlchemy ORM
        objects directly.
        """
        orm_mode = True