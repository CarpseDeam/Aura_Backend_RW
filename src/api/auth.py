# src/api/auth.py
"""
API routes for user authentication, including registration, login (token generation),
and retrieving the current authenticated user.
"""
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
    """
    Handles user registration.

    Creates a new user in the database if the email is not already in use.
    It now requires a valid beta key.

    Args:
        user_in: The user data for registration from the request body.
        db: The database session dependency.

    Returns:
        The newly created user's data.

    Raises:
        HTTPException: If the beta key is invalid or the email already exists.
    """
    # --- NEW: Beta Key Validation ---
    if user_in.beta_key != config.settings.BETA_ACCESS_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Beta Key",
        )

    db_user = crud.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return crud.create_user(db=db, user=user_in)

@router.post("/token", response_model=token.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict:
    """
    Authenticates a user and returns a JWT access token.

    Uses OAuth2 password flow. The client sends username and password in a form.

    Args:
        form_data: The OAuth2 password request form, containing username and password.
        db: The database session dependency.

    Returns:
        A dictionary containing the access token and token type.

    Raises:
        HTTPException: If authentication fails (incorrect email or password).
    """
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
    """
    Dependency to get the current authenticated user from a JWT token.

    Decodes the JWT token from the Authorization header, validates its claims,
    and fetches the corresponding user from the database.

    Args:
        token_str: The JWT token from the Authorization header.
        db: The database session dependency.

    Returns:
        The authenticated user model instance.

    Raises:
        HTTPException: If the token is invalid, expired, or the user is not found.
    """
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
    """
    Fetches the details of the currently authenticated user.

    This is a protected endpoint that requires a valid JWT access token.

    Args:
        current_user: The user object injected by the get_current_user dependency.

    Returns:
        The current user's data.
    """
    return current_user