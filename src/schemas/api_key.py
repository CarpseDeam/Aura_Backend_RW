# src/schemas/api_key.py
"""Pydantic schemas for multi-provider API Key validation."""

from pydantic import BaseModel, ConfigDict
from typing import List

class ProviderKeyBase(BaseModel):
    """Base schema for provider key properties."""
    provider_name: str

class ProviderKeyCreate(ProviderKeyBase):
    """Schema used when a user submits a new API key."""
    api_key: str

class ProviderKey(ProviderKeyBase):
    """Schema for representing a configured API key in API responses."""
    masked_key: str
    model_config = ConfigDict(from_attributes=True)


class ProviderKeyList(BaseModel):
    """Schema for returning a list of configured keys."""
    keys: List[ProviderKey]
    model_config = ConfigDict(from_attributes=True)