# src/api/keys.py
from typing import Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.db import crud, models
from src.db.database import get_db
from src.schemas import api_key
from src.api.auth import get_current_user

router = APIRouter(tags=["API Keys"])

@router.put("/keys", response_model=Dict[str, str], status_code=status.HTTP_200_OK)
def update_user_api_key(api_key_data: api_key.ApiKey, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)) -> Dict[str, str]:
    crud.update_api_key(db=db, user=current_user, api_key=api_key_data.api_key)
    return {"message": "API key updated successfully"}