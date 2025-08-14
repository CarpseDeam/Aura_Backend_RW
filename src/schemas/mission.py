# src/schemas/mission.py
"""Pydantic schemas for mission task interactions."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Task(BaseModel):
    """Represents a single task in the mission log for API responses."""
    id: int
    description: str
    done: bool
    tool_call: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None

    class Config:
        from_attributes = True

class TaskCreateRequest(BaseModel):
    """Schema for creating a new task."""
    description: str = Field(..., min_length=1)

class TaskUpdateRequest(BaseModel):
    """Schema for updating a task's description."""
    description: str = Field(..., min_length=1)

class TasksReorderRequest(BaseModel):
    """Schema for reordering tasks."""
    ordered_task_ids: List[int]