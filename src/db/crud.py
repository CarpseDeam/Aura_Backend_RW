# src/db/crud.py
from sqlalchemy.orm import Session

from src.db import models
from src.schemas import user

def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user_in: user.UserCreate) -> models.User:
    from src.core.security import get_password_hash
    hashed_password = get_password_hash(user_in.password)
    db_user = models.User(email=user_in.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_api_key(db: Session, user: models.User, api_key: str) -> models.User:
    from src.core.security import encrypt_data, settings
    encrypted_key = encrypt_data(api_key.encode('utf-8'), settings.ENCRYPTION_KEY)
    user.encrypted_openai_api_key = encrypted_key
    db.add(user)
    db.commit()
    db.refresh(user)
    return user