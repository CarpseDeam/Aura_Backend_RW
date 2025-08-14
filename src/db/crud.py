# src/db/crud.py
"""
This module contains reusable functions for database CRUD operations.

It provides a layer of abstraction over the database models, allowing the rest
of the application to interact with the database in a consistent and secure way.
"""
from sqlalchemy.orm import Session
from typing import Dict, List

from src.core import security, config
from src.db import models
from src.schemas import user


def get_user_by_email(db: Session, email: str) -> models.User | None:
    """Fetches a user from the database by their email address."""
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: user.UserCreate) -> models.User:
    """Creates a new user in the database."""
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
    """Creates or updates a provider key, encrypting the API key."""
    encrypted_key = security.encrypt_data(api_key.encode('utf-8'), config.settings.ENCRYPTION_KEY)
    db_key = get_provider_key(db, user_id=user_id, provider_name=provider_name)
    if db_key:
        db_key.encrypted_key = encrypted_key
    else:
        db_key = models.ProviderKey(user_id=user_id, provider_name=provider_name, encrypted_key=encrypted_key)
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


# --- Model Assignment CRUD Functions ---

def get_assignments_for_user(db: Session, user_id: int) -> List[models.ModelAssignment]:
    """Fetches all model assignments for a user."""
    return db.query(models.ModelAssignment).filter(models.ModelAssignment.user_id == user_id).all()


def create_or_update_assignments_for_user(db: Session, user_id: int, assignments: Dict[str, str]):
    """
    Atomically updates all model assignments for a user.
    `assignments` is a dict of {"role_name": "provider/model_name"}.
    """
    existing_assignments = {a.role_name: a for a in get_assignments_for_user(db, user_id)}

    for role_name, model_identifier in assignments.items():
        if role_name in existing_assignments:
            # Update existing assignment
            existing_assignments[role_name].model_identifier = model_identifier
        else:
            # Create new assignment
            new_assignment = models.ModelAssignment(
                user_id=user_id,
                role_name=role_name,
                model_identifier=model_identifier
            )
            db.add(new_assignment)
    db.commit()