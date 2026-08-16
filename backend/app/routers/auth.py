from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)

from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate and obtain an access token",
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db,
        credentials.username,
        credentials.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    access_token = create_access_token(user)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post(
    "/logout",
    summary="Log out the current session",
)
def logout(
    current_user: User = Depends(get_current_user),
):
    """
    Stateless JWT: the backend holds no server-side session to
    invalidate, and no token-revocation mechanism exists in this
    phase. This endpoint confirms the caller was authenticated at
    call time; it does not (and cannot) invalidate the token itself.
    The client is responsible for discarding the token.
    """

    return {
        "detail": (
            "Logged out. Discard the access token client-side - "
            "this token is not server-side revoked and remains "
            "valid until it expires."
        ),
    }
