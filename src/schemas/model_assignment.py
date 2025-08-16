# src/schemas/model_assignment.py
"""Pydantic schemas for model assignments."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List


class AvailableModels(BaseModel):
    """Schema for returning a list of available models grouped by provider."""
    models: Dict[str, List[str]]


class ModelAssignment(BaseModel):
    """Represents a single model assignment for a role."""
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)
    role_name: str
    model_id: str
    temperature: float = Field(..., ge=0.0, le=2.0)


class ModelAssignmentList(BaseModel):
    """A list of model assignments, used for retrieving all assignments for a user."""
    assignments: List[ModelAssignment]
    model_config = ConfigDict(from_attributes=True)


class ModelAssignmentUpdate(BaseModel):
    """
    Schema for updating all model assignments for a user in one request.
    It now accepts a list of assignment objects.
    """
    assignments: List[ModelAssignment]