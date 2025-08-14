# src/schemas/model_assignment.py
"""Pydantic schemas for model assignments."""
from pydantic import BaseModel
from typing import Dict, List


class ModelAssignment(BaseModel):
    """Represents a single model assignment for a role."""
    role_name: str
    model_identifier: str

    class Config:
        """Pydantic configuration options."""
        from_attributes = True


class ModelAssignmentList(BaseModel):
    """A list of model assignments, used for retrieving all assignments for a user."""
    assignments: List[ModelAssignment]

    class Config:
        """Pydantic configuration options."""
        from_attributes = True


class ModelAssignmentUpdate(BaseModel):
    """
    Schema for updating all model assignments for a user in one request.
    """
    assignments: Dict[str, str]


class AvailableModels(BaseModel):
    """
    Represents the structure of available models, grouped by provider.
    """
    models: Dict[str, List[str]]