# src/api/assignments.py
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List

from src.db import crud, models
from src.db.database import get_db
from src.schemas import model_assignment as schemas
from src.api.auth import get_current_user

router = APIRouter(tags=["Model Assignments"])

# This dictionary defines the next-gen models available for each provider.
# This is our "future-proof" list.
NEXT_GEN_MODELS: Dict[str, List[str]] = {
    "openai": ["gpt-5"],
    "google": ["gemini-2.5-pro", "gemini-2.5-flash"],
    "anthropic": ["claude-4.1"],
    "deepseek": ["deepseek-reasoning"],
}


@router.get("/available-models", response_model=schemas.AvailableModels)
def get_available_models(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Get a list of available models a user can assign to roles,
    based on the API keys they have configured.
    """
    configured_keys = crud.get_provider_keys_for_user(db, user_id=current_user.id)
    configured_providers = {key.provider_name for key in configured_keys}

    available_models: Dict[str, List[str]] = {}
    for provider, models_list in NEXT_GEN_MODELS.items():
        if provider in configured_providers:
            available_models[provider] = models_list

    return schemas.AvailableModels(models=available_models)


@router.get("/", response_model=schemas.ModelAssignmentList)
def get_user_assignments(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """Retrieve all model assignments for the current user."""
    db_assignments = crud.get_assignments_for_user(db, user_id=current_user.id)
    return schemas.ModelAssignmentList(assignments=db_assignments)


@router.post("/", status_code=status.HTTP_204_NO_CONTENT)
def update_user_assignments(
        assignments_in: schemas.ModelAssignmentUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Update all model assignments for the current user in a single transaction.
    """
    try:
        crud.create_or_update_assignments_for_user(db, user_id=current_user.id, assignments=assignments_in.assignments)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while saving assignments: {e}"
        )
    return None  # Return empty response for 204