# src/db/database.py
"""
Database session management for the application.

This module sets up the SQLAlchemy engine and session management. It provides a
dependency (`get_db`) for FastAPI to inject a database session into path
operation functions.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from src.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# The `connect_args` parameter is ONLY for SQLite and will cause a crash with PostgreSQL.
# It has been removed.
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy database session.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()