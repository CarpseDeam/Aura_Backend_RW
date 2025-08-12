# src/schemas/token.py
"""
Pydantic models related to JWT authentication.

This module defines the data structures for handling JWT tokens, including the
response format for a token request and the data payload encoded within a token.
"""

from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """
    Represents the response model for a successful token request.
    """
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """
    Represents the data payload encoded within a JWT.

    This schema is used to validate the 'sub' (subject) claim, which contains the user's email.
    """
    email: Optional[str] = None