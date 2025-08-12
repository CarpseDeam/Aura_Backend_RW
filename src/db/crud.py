# src/db/crud.py
"""
This module contains reusable functions for database CRUD operations.

It provides a layer of abstraction over the database models, allowing the rest
of the application to interact with the database in a consistent and secure way.
"""

from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import get_password_hash, encrypt_data
from . import models
from .. import schemas


def get_user_by_email(db: Session, email: str) -> models.User | None:
    """
    Fetches a user from the database by their email address.

    Args:
        db: The SQLAlchemy database session.
        email: The email address of the user to retrieve.

    Returns:
        The User model instance if found, otherwise None.
    """
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.user.UserCreate) -> models.User:
    """
    Creates a new user in the database.

    This function takes user creation data, hashes the password for security,
    and persists the new user record to the database.

    Args:
        db: The SQLAlchemy database session.
        user: A Pydantic schema containing the user's details (email, password).

    Returns:
        The newly created User model instance, including its database-generated ID.
    """
    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_api_key(db: Session, user: models.User, api_key: str) -> models.User:
    """
    Updates a user's encrypted OpenAI API key.

    Encrypts the provided plaintext API key and saves it to the user's
    record in the database.

    Args:
        db: The SQLAlchemy database session.
        user: The User model instance to update.
        api_key: The new, plaintext OpenAI API key to encrypt and store.

    Returns:
        The updated User model instance.
    """
    # The encryption utility expects bytes, so we encode the string.
    encrypted_key = encrypt_data(
        api_key.encode('utf-8'),
        settings.ENCRYPTION_KEY
    )
    user.encrypted_openai_api_key = encrypted_key
    db.add(user)
    db.commit()
    db.refresh(user)
    return user