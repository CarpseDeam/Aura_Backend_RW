"""Pydantic schemas for API Key validation.

This module defines the Pydantic models used for validating and serializing
API key data in the application's API.
"""

from pydantic import BaseModel


class ApiKey(BaseModel):
    """Schema for representing an API key.

    This model is used to validate incoming requests that require an API key
    in the request body.

    Attributes:
        api_key: The string representation of the API key.
    """
    api_key: str