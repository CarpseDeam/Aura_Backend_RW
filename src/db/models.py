# src/db/models.py
"""
Defines the SQLAlchemy ORM models for the database.

This module contains the class definitions that map to database tables.
Each class represents a table, and its attributes represent the columns.
"""

from sqlalchemy import Column, Integer, String, LargeBinary
from .database import Base


class User(Base):
    """
    Represents a user in the 'users' table.

    This model stores user authentication and configuration details.

    Attributes:
        id (int): The primary key for the user, auto-incrementing.
        email (str): The user's unique email address, used for login.
        hashed_password (str): The user's password, hashed for security.
        encrypted_openai_api_key (bytes, optional): The user's OpenAI API key,
            encrypted before being stored in the database. Can be None if not
            provided by the user.
    """
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    email: str = Column(String, unique=True, index=True, nullable=False)
    hashed_password: str = Column(String, nullable=False)
    encrypted_openai_api_key: bytes = Column(LargeBinary, nullable=True)