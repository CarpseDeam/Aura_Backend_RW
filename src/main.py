"""
Main application file for the Secure API Key Manager.

This file initializes the FastAPI application, includes the necessary API routers,
and defines a root endpoint.
"""

from typing import Dict

from fastapi import FastAPI

from src.api.auth import router as auth_router
from src.api.keys import router as keys_router

app = FastAPI(
    title="Secure API Key Manager",
    description="A robust and secure system for creating, managing, and validating API keys.",
    version="1.0.0",
)

# Include the routers from the api modules with appropriate prefixes and tags
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(keys_router, prefix="/api-keys", tags=["API Keys"])


@app.get("/", response_model=Dict[str, str], tags=["Root"])
async def read_root() -> Dict[str, str]:
    """
    Root GET endpoint.

    Provides a simple welcome message to verify that the service is running.

    Returns:
        Dict[str, str]: A dictionary containing a welcome message.
    """
    return {"message": "Welcome to the Secure API Key Manager"}