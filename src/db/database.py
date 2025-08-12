"""
Database session management for the application.

This module sets up the SQLAlchemy engine and session management. It provides a
dependency (`get_db`) for FastAPI to inject a database session into path
operation functions.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from src.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
"""
The full database connection string, read from application settings.
"""

# The `connect_args` is a workaround needed only for SQLite.
# SQLite by default only allows one thread to communicate with it, assuming that
# each thread would be a separate request. FastAPI, with its async nature, can
# have multiple threads interacting with the database for a single request,
# so we need to disable this check.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
"""
The core SQLAlchemy engine for database communication.
"""

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
"""
A factory for creating new database session objects.
"""

Base = declarative_base()
"""
A base class for all ORM models. All model classes should inherit from this class.
"""


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy database session.

    This function is a generator that creates a new `SessionLocal` instance for
    each request, yields it to the path operation function, and then ensures
    that the session is closed after the request is finished, even if an error
    occurred during processing.

    Yields:
        Generator[Session, None, None]: A SQLAlchemy Session object that can be used
        to interact with the database.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()