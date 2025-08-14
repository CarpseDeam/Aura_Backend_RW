# src/db/models.py
"""
Defines the SQLAlchemy ORM models for the database.

This module contains the class definitions that map to database tables.
Each class represents a table, and its attributes represent the columns.
"""

from sqlalchemy import Column, Integer, String, LargeBinary, ForeignKey, UniqueConstraint, Float
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    """
    Represents a user in the 'users' table.
    """
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    email: str = Column(String, unique=True, index=True, nullable=False)
    hashed_password: str = Column(String, nullable=False)

    keys = relationship("ProviderKey", back_populates="owner", cascade="all, delete-orphan")
    assignments = relationship("ModelAssignment", back_populates="owner", cascade="all, delete-orphan")


class ProviderKey(Base):
    """
    Represents an encrypted API key for a specific provider, linked to a user.
    """
    __tablename__ = "provider_keys"

    id: int = Column(Integer, primary_key=True, index=True)
    provider_name: str = Column(String, index=True, nullable=False)
    encrypted_key: bytes = Column(LargeBinary, nullable=False)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="keys")

    __table_args__ = (UniqueConstraint('user_id', 'provider_name', name='_user_provider_uc'),)


class ModelAssignment(Base):
    """
    Represents a user's choice of a specific model for a specific role.
    """
    __tablename__ = "model_assignments"

    id: int = Column(Integer, primary_key=True, index=True)
    role_name: str = Column(String, index=True, nullable=False)
    model_identifier: str = Column(String, nullable=False)  # e.g., "openai/gpt-5"
    temperature: float = Column(Float, nullable=False, server_default='0.7') # <-- NEW
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="assignments")

    __table_args__ = (UniqueConstraint('user_id', 'role_name', name='_user_role_uc'),)