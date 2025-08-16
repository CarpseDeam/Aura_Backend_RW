# src/core/config.py
"""
Manages application configuration using Pydantic's BaseSettings.

This module defines a `Settings` class that loads environment variables
from a .env file, providing a centralized and validated source of
configuration for the entire application.
"""
import sys
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic's BaseSettings class handles the loading and validation of these
    settings from the environment or a .env file.

    Attributes:
        DATABASE_URL (str): The connection string for the primary database.
        JWT_SECRET_KEY (str): The secret key for signing and verifying JSON Web Tokens.
        ENCRYPTION_KEY (str): A secret key for symmetric encryption/decryption of data.
        BETA_ACCESS_KEY (str): A secret key required for new user registration.
        ALGORITHM (str): The algorithm to use for JWT encoding (e.g., "HS256").
        ACCESS_TOKEN_EXPIRE_MINUTES (int): The lifetime of an access token in minutes.
    """
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    ENCRYPTION_KEY: str
    BETA_ACCESS_KEY: str  # <-- NEW: The required beta key
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # THIS IS THE FIX: Explicitly disable .env file loading.
    # This forces Pydantic to ONLY use environment variables, which is
    # the correct behavior for a containerized deployment on Railway.
    model_config = SettingsConfigDict(env_file=None)


# Create a single, globally accessible instance of the settings.
# Other modules can import this instance to access configuration values.
try:
    settings = Settings()
except ValidationError as e:
    # This error handling is critical for deployment. If the app crashes
    # silently, it's almost always because an environment variable is missing.
    # This block makes the error loud and clear in the logs.
    print("="*80, file=sys.stderr)
    print("!!! AURA BACKEND: FATAL ERROR - MISSING ENVIRONMENT VARIABLES !!!", file=sys.stderr)
    print("="*80, file=sys.stderr)
    print("The application failed to start because one or more required environment", file=sys.stderr)
    print("variables are not set in the Railway deployment environment.", file=sys.stderr)
    print("\nDETAILS:", file=sys.stderr)
    print(e, file=sys.stderr)
    print("\nACTION REQUIRED:", file=sys.stderr)
    print("Go to your Railway project -> aura-backend service -> Variables", file=sys.stderr)
    print("and ensure all of the following are set:", file=sys.stderr)
    print("- DATABASE_URL", file=sys.stderr)
    print("- JWT_SECRET_KEY", file=sys.stderr)
    print("- ENCRYPTION_KEY", file=sys.stderr)
    print("- BETA_ACCESS_KEY", file=sys.stderr)
    print("="*80, file=sys.stderr)
    sys.exit(1) # Exit with a failure code to make the crash obvious.