# src/api/keys.py
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from src.db import crud, models
from src.db.database import get_db
from src.schemas import api_key as schemas
from src.api.auth import get_current_user

router = APIRouter(tags=["Provider Keys"])


def mask_api_key(key: str) -> str:
    """Masks an API key for safe display, showing first and last few chars."""
    if not key:
        return "ERROR_NO_KEY"
    if len(key) < 8:
        return "********"

    parts = key.split('_')
    if len(parts) > 1:
        prefix = parts[0]
        suffix = parts[-1]
        return f"{prefix}_...{suffix[-4:]}"
    else:
        # For keys without underscores
        return f"{key[:4]}...{key[-4:]}"


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ProviderKey)
def create_or_update_key(
        key_in: schemas.ProviderKeyCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
):
    """
    Create a new API key for a specific provider or update an existing one.
    The key will be encrypted before storage.
    """
    provider_name = key_in.provider_name.lower().strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="Provider name cannot be empty.")

    db_key = crud.create_or_update_provider_key(
        db=db,
        user_id=current_user.id,
        provider_name=provider_name,
        api_key=key_in.api_key
    )

    return schemas.ProviderKey(
        provider_name=db_key.provider_name,
        masked_key=mask_api_key(key_in.api_key)  # Mask the raw key for immediate response
    )


@router.get("/", response_model=schemas.ProviderKeyList)
def get_user_keys(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
):
    """
    Retrieve all configured API keys for the current user, in a masked format.
    """
    db_keys = crud.get_provider_keys_for_user(db, user_id=current_user.id)

    response_keys = []
    for db_key in db_keys:
        # Decrypt temporarily to mask it for display
        decrypted_key = crud.get_decrypted_key_for_provider(db, user_id=current_user.id,
                                                            provider_name=db_key.provider_name)
        if decrypted_key:
            response_keys.append(
                schemas.ProviderKey(
                    provider_name=db_key.provider_name,
                    masked_key=mask_api_key(decrypted_key)
                )
            )

    return schemas.ProviderKeyList(keys=response_keys)


@router.delete("/{provider_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key(
        provider_name: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
):
    """
    Delete an API key for a specific provider.
    """
    deleted = crud.delete_provider_key_for_user(
        db, user_id=current_user.id, provider_name=provider_name.lower().strip()
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key for provider '{provider_name}' not found."
        )
    return None  # Return empty response for 204