# src/core/security.py
"""
Handles security-related functions for the application.

This module provides functionalities for password hashing and verification,
JSON Web Token (JWT) creation, and API key encryption/decryption using Fernet.
"""

from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db import crud, models

# 1. Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a plain text password using bcrypt."""
    return pwd_context.hash(password)


# 2. User Authentication
def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    """
    Authenticates a user by checking their email and password.

    Args:
        db: The database session.
        email: The user's email.
        password: The user's plaintext password.

    Returns:
        The User object if authentication is successful, otherwise None.
    """
    user = crud.get_user_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# 3. JWT Handling
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


# 4. API Key Encryption/Decryption
def encrypt_data(data: bytes, key: str) -> bytes:
    """Encrypts data using the application's encryption key."""
    fernet = Fernet(key.encode())
    return fernet.encrypt(data)


def decrypt_data(encrypted_data: bytes, key: str) -> bytes:
    """Decrypts data using the application's encryption key."""
    fernet = Fernet(key.encode())
    return fernet.decrypt(encrypted_data)