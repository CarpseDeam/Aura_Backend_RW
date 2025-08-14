# src/schemas/model_assignment.py
"""Pydantic schemas for model assignments."""
from pydantic import BaseModel
from typing import Dict, List

class ModelAssignment(BaseModel):
    """Represents a single model assignment for a role."""
    role_name: str
    model_identifier: str

class ModelAssignmentList(BaseModel):
    """A list of model assignments, used for retrieving all assignments for a user."""
    assignments: List[ModelAssignment]

class ModelAssignmentUpdate(BaseModel):
    """
    Schema for updating all model assignments for a user in one request.
    The keys are the role names (e.g., "planner") and values are the model identifiers (e.g., "openai/gpt-5").
    """
    assignments: Dict[str, str]

class AvailableModels(BaseModel):
    """
    Represents the structure of available models, grouped by provider, that a user can choose from.
    """
    models: Dict[str, List[str]]