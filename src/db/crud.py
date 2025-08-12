# src/db/crud.py
"""
This module contains reusable functions for database CRUD operations.

It provides a layer of abstraction over the database models, allowing the rest
of the application to interact with the database in a consistent and secure way.
"""

from sqlalchemy.orm import Session

from ..core.config import settings
from . import models
from .. import schemas


def get_user_by_email(db: Session, email: str) -> models.User | None:
    """Fetches a user from the database by their email address."""
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.user.UserCreate) -> models.User:
    """Creates a new user in the database."""
    # <-- THIS IS THE FIX: We import the function here, inside the function that uses it.
    from src.core.security import get_password_hash

    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_api_key(db: Session, user: models.User, api_key: str) -> models.User:
    """Updates a user's encrypted OpenAI API key."""
    from src.core.security import encrypt_data

    encrypted_key = encrypt_data(
        api_key.encode('utf-8'),
        settings.ENCRYPTION_KEY
    )
    user.encrypted_openai_api_key = encrypted_key
    db.add(user)
    db.commit()
    db.refresh(user)
    return user