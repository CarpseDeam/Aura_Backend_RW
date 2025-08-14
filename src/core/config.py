# src/core/config.py
"""
Manages application configuration using Pydantic's BaseSettings.

This module defines a `Settings` class that loads environment variables
from a .env file, providing a centralized and validated source of
configuration for the entire application.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic's BaseSettings class handles the loading and validation of these
    settings from the environment or a .env file.

    Attributes:
        DATABASE_URL (str): The connection string for the primary database.
        JWT_SECRET_KEY (str): The secret key for signing and verifying JSON Web Tokens.
        ENCRYPTION_KEY (str): A secret key for symmetric encryption/decryption of data.
        ALGORITHM (str): The algorithm to use for JWT encoding (e.g., "HS256").
        ACCESS_TOKEN_EXPIRE_MINUTES (int): The lifetime of an access token in minutes.
    """
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    ENCRYPTION_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        """Pydantic configuration options for the Settings class."""
        # The env_file directive is removed to rely solely on environment variables
        # in production, which is the standard for platforms like Railway.
        env_file_encoding = "utf-8"


# Create a single, globally accessible instance of the settings.
# Other modules can import this instance to access configuration values.
settings = Settings()