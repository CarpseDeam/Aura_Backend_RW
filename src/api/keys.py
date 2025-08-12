# src/api/keys.py
"""
API router for managing user-specific API keys.

This module provides an endpoint for users to update their external service
API keys, such as the OpenAI API key. The key is encrypted before being
stored in the database.
"""

from typing import Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.db import crud, models
from src.db.database import get_db
from src.schemas import api_key as api_key_schema
from src.schemas import user as user_schema
from src.api.auth import get_current_user

router = APIRouter(
    tags=["API Keys"],
    responses={404: {"description": "Not found"}},
)


@router.put("/keys", response_model=Dict[str, str], status_code=status.HTTP_200_OK)
def update_user_api_key(
    api_key_data: api_key_schema.ApiKey,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Update the OpenAI API key for the currently authenticated user.

    This endpoint receives the new API key, encrypts it for security,
    and then updates the corresponding record in the database for the
    logged-in user.

    Args:
        api_key_data: The request body containing the new OpenAI API key.
        db: The database session, injected by FastAPI's dependency system.
        current_user: The authenticated user object, injected by the
                      `get_current_user` dependency.

    Returns:
        A dictionary containing a success message.
    """
    crud.update_api_key(
        db=db, user=current_user, api_key=api_key_data.api_key
    )

    return {"message": "API key updated successfully"}