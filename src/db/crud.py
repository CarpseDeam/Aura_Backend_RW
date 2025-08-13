# src/db/crud.py
"""
This module contains reusable functions for database CRUD operations.

It provides a layer of abstraction over the database models, allowing the rest
of the application to interact with the database in a consistent and secure way.
"""
from sqlalchemy.orm import Session

from src.core import security, config
from src.db import models
from src.schemas import user


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


def create_user(db: Session, user: user.UserCreate) -> models.User:
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
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# --- Provider Key CRUD Functions ---

def get_provider_key(db: Session, user_id: int, provider_name: str) -> models.ProviderKey | None:
    """Fetches a specific provider key for a user."""
    return db.query(models.ProviderKey).filter(
        models.ProviderKey.user_id == user_id,
        models.ProviderKey.provider_name == provider_name
    ).first()


def get_provider_keys_for_user(db: Session, user_id: int) -> list[models.ProviderKey]:
    """Fetches all provider keys for a user."""
    return db.query(models.ProviderKey).filter(models.ProviderKey.user_id == user_id).all()


def create_or_update_provider_key(db: Session, user_id: int, provider_name: str, api_key: str) -> models.ProviderKey:
    """
    Creates a new provider key or updates it if it already exists for the user.
    The API key is encrypted before being stored.
    """
    encrypted_key = security.encrypt_data(api_key.encode('utf-8'), config.settings.ENCRYPTION_KEY)

    db_key = get_provider_key(db, user_id=user_id, provider_name=provider_name)

    if db_key:
        # Update existing key
        db_key.encrypted_key = encrypted_key
    else:
        # Create new key
        db_key = models.ProviderKey(
            user_id=user_id,
            provider_name=provider_name,
            encrypted_key=encrypted_key
        )
        db.add(db_key)

    db.commit()
    db.refresh(db_key)
    return db_key


def delete_provider_key_for_user(db: Session, user_id: int, provider_name: str) -> bool:
    """Deletes a specific provider key for a user."""
    db_key = get_provider_key(db, user_id=user_id, provider_name=provider_name)
    if db_key:
        db.delete(db_key)
        db.commit()
        return True
    return False


def get_decrypted_key_for_provider(db: Session, user_id: int, provider_name: str) -> str | None:
    """Fetches and decrypts a specific provider key for a user, ready for use."""
    db_key = get_provider_key(db, user_id=user_id, provider_name=provider_name)
    if db_key:
        decrypted_key = security.decrypt_data(db_key.encrypted_key, config.settings.ENCRYPTION_KEY)
        return decrypted_key.decode('utf-8')
    return None