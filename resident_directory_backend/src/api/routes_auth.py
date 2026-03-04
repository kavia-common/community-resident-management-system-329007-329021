"""
Authentication routes.

Flow: AuthRouteFlow
- POST /api/auth/login — authenticate user, return JWT
- POST /api/auth/register — create new user (admin only)
- GET /api/auth/me — get current user profile

Contract:
  Input: LoginRequest for login; UserCreate for register; Bearer token for me
  Output: TokenResponse, UserResponse
  Errors: 401 invalid credentials; 403 insufficient role; 409 duplicate user
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.api.auth import (
    verify_password,
    hash_password,
    create_access_token,
    get_current_user,
    require_admin,
)
from src.api.database import get_db
from src.api.models import User
from src.api.schemas import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from src.api.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# PUBLIC_INTERFACE
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate with username and password to receive a JWT access token.",
    responses={401: {"description": "Invalid credentials"}},
)
def login(request_body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Authenticate a user with username and password.

    Returns a JWT access token on success.
    """
    logger.info("Login attempt for user: %s", request_body.username)

    user = db.query(User).filter(User.username == request_body.username).first()
    if user is None or not verify_password(request_body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    log_action(
        db=db,
        user_id=user.id,
        action="LOGIN",
        entity_type="user",
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user.id),
        username=user.username,
        role=user.role,
    )


# PUBLIC_INTERFACE
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account. Only admins can create new users.",
    responses={409: {"description": "Username or email already exists"}},
)
def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Register a new user account (admin only).

    Creates a new user with hashed password and specified role.
    """
    logger.info("Admin %s registering new user: %s", current_user.username, user_data.username)

    # Check for duplicate username
    existing = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    # Validate role
    if user_data.role not in ("admin", "resident"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin' or 'resident'",
        )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_action(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        entity_type="user",
        entity_id=new_user.id,
        details={"username": new_user.username, "role": new_user.role},
        ip_address=request.client.host if request.client else None,
    )

    return new_user


# PUBLIC_INTERFACE
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the profile of the currently authenticated user.",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return current_user


# PUBLIC_INTERFACE
@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List all users",
    description="Returns all users. Admin only.",
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all user accounts (admin only)."""
    return db.query(User).order_by(User.created_at.desc()).all()


# PUBLIC_INTERFACE
@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update a user's email, role, or active status. Admin only.",
)
def update_user(
    user_id: str,
    user_data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an existing user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_fields = user_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    log_action(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        entity_type="user",
        entity_id=user.id,
        details={"updated_fields": list(update_fields.keys())},
        ip_address=request.client.host if request.client else None,
    )

    return user
