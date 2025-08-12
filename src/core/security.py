# src/core/security.py

"""
Handles security-related functions for the application.

This module provides functionalities for password hashing and verification,
JSON Web Token (JWT) creation, and API key encryption/decryption using Fernet.
"""

from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import settings

# 1. Password Hashing
# Context for creating and verifying password hashes.
# Uses bcrypt as the default scheme.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against a hashed password.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The hashed password from the database.

    Returns:
        True if the password is a match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hashes a plain text password using bcrypt.

    Args:
        password: The plain text password to hash.

    Returns:
        The hashed password as a string.
    """
    return pwd_context.hash(password)


# 2. JWT Handling
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT access token.

    The token includes the provided data and an expiration timestamp.

    Args:
        data: A dictionary of claims to include in the token payload.
        expires_delta: An optional timedelta object for token expiration.
                       If not provided, defaults to 15 minutes.

    Returns:
        The encoded JWT as a string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


# 3. API Key Encryption/Decryption
def encrypt_api_key(api_key: str) -> str:
    """
    Encrypts a plaintext API key using Fernet symmetric encryption.

    Args:
        api_key: The plaintext API key to encrypt.

    Returns:
        The encrypted key, URL-safe and encoded as a UTF-8 string.
    """
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted_key = fernet.encrypt(api_key.encode())
    return encrypted_key.decode()


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypts an encrypted API key.

    Args:
        encrypted_api_key: The encrypted key string.

    Returns:
        The decrypted, plaintext API key as a string.
    """
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    decrypted_key = fernet.decrypt(encrypted_api_key.encode())
    return decrypted_key.decode()