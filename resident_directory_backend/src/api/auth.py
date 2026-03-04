"""
Authentication and authorization module.

Flow: AuthenticationFlow
- Handles password hashing/verification using bcrypt via passlib.
- Creates and validates JWT tokens using python-jose.
- Provides FastAPI dependencies for route-level auth and RBAC.

Contract:
  Input: username/password for login; JWT token for authenticated requests
  Output: TokenResponse on login; User object on authenticated requests
  Errors: HTTPException 401 for invalid credentials/tokens; 403 for insufficient role
  Side effects: None (stateless JWT)

Invariants:
  - JWT_SECRET_KEY must be set (falls back to a default in dev only)
  - Tokens expire after JWT_ACCESS_TOKEN_EXPIRE_MINUTES (default 480 = 8 hours)
  - Password verification uses bcrypt
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import User

logger = logging.getLogger(__name__)

# --- Configuration ---
# JWT_SECRET_KEY should be set via environment variable in production
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token security scheme
security = HTTPBearer()


# PUBLIC_INTERFACE
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a bcrypt hash.

    Args:
        plain_password: The plain-text password to verify.
        hashed_password: The bcrypt hash to verify against.

    Returns:
        True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain-text password to hash.

    Returns:
        Bcrypt hash string.
    """
    return pwd_context.hash(password)


# PUBLIC_INTERFACE
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token.
        expires_delta: Optional custom expiration timedelta.

    Returns:
        Encoded JWT token string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.debug("Created access token for sub=%s, expires=%s", data.get("sub"), expire)
    return encoded_jwt


# PUBLIC_INTERFACE
def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Args:
        token: Encoded JWT token string.

    Returns:
        Dictionary of decoded claims.

    Raises:
        HTTPException: 401 if token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# PUBLIC_INTERFACE
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency to get the current authenticated user from the JWT token.

    Args:
        credentials: Bearer token from request header.
        db: Database session.

    Returns:
        The authenticated User ORM object.

    Raises:
        HTTPException: 401 if token is invalid or user not found.
    """
    payload = decode_access_token(credentials.credentials)
    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed user ID",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


# PUBLIC_INTERFACE
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency that requires the current user to have admin role.

    Args:
        current_user: The authenticated user (from get_current_user).

    Returns:
        The admin User object.

    Raises:
        HTTPException: 403 if user is not an admin.
    """
    if current_user.role != "admin":
        logger.warning(
            "Non-admin user %s attempted admin action", current_user.username
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
