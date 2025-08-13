# src/db/models.py
"""
Defines the SQLAlchemy ORM models for the database.

This module contains the class definitions that map to database tables.
Each class represents a table, and its attributes represent the columns.
"""

from sqlalchemy import Column, Integer, String, LargeBinary, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    """
    Represents a user in the 'users' table.

    This model stores user authentication and configuration details.

    Attributes:
        id (int): The primary key for the user, auto-incrementing.
        email (str): The user's unique email address, used for login.
        hashed_password (str): The user's password, hashed for security.
        keys (relationship): A one-to-many relationship to the user's provider API keys.
    """
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    email: str = Column(String, unique=True, index=True, nullable=False)
    hashed_password: str = Column(String, nullable=False)

    keys = relationship("ProviderKey", back_populates="owner", cascade="all, delete-orphan")


class ProviderKey(Base):
    """
    Represents an encrypted API key for a specific provider, linked to a user.

    Attributes:
        id (int): The primary key for the key entry.
        provider_name (str): The name of the API provider (e.g., "openai", "anthropic").
        encrypted_key (bytes): The user's API key, encrypted before being stored.
        user_id (int): Foreign key linking to the user who owns this key.
        owner (relationship): The back-reference to the User object.
    """
    __tablename__ = "provider_keys"

    id: int = Column(Integer, primary_key=True, index=True)
    provider_name: str = Column(String, index=True, nullable=False)
    encrypted_key: bytes = Column(LargeBinary, nullable=False)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="keys")

    __table_args__ = (UniqueConstraint('user_id', 'provider_name', name='_user_provider_uc'),)