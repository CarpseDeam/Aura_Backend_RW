# src/api/keys.py

"""
API router for managing user-specific API keys.

This module provides an endpoint for users to update their external service
API keys, such as the OpenAI API key. The key is encrypted before being
stored in the database.
"""

from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.security import encrypt_data
from ..db.crud import update_api_key
from ..db.database import get_db
from ..schemas.api_key import APIKeyUpdate
from ..schemas.user import User
from .auth import get_current_active_user

router = APIRouter(
    prefix="/keys",
    tags=["API Keys"],
    responses={404: {"description": "Not found"}},
)


@router.put("/", response_model=Dict[str, str])
def update_user_api_key(
    api_key_data: APIKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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
                      `get_current_active_user` dependency.

    Returns:
        A dictionary containing a success message.
    """
    encrypted_api_key = encrypt_data(api_key_data.openai_api_key)

    update_api_key(
        db=db, user_id=current_user.id, encrypted_api_key=encrypted_api_key
    )

    return {"message": "API key updated successfully"}