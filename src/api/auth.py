# src/api/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.core import config, security
from src.db import crud, models
from src.db.database import get_db
from src.schemas import token, user

router = APIRouter(tags=["auth"])

@router.post("/register", response_model=user.User, status_code=status.HTTP_201_CREATED)
async def register(user_in: user.UserCreate, db: Session = Depends(get_db)) -> models.User:
    db_user = crud.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return crud.create_user(db=db, user=user_in)

@router.post("/token", response_model=token.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict:
    user_auth = security.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(data={"sub": user_auth.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_user(token_str: str = Depends(security.oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token_str, config.settings.JWT_SECRET_KEY, algorithms=[config.settings.ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = token.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user_obj = crud.get_user_by_email(db, email=token_data.email)
    if user_obj is None:
        raise credentials_exception
    return user_obj

@router.get("/users/me", response_model=user.User)
async def read_users_me(current_user: models.User = Depends(get_current_user)) -> models.User:
    return current_user