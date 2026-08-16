from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User

from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)

from app.services.auth import (
    authenticate_user,
    change_password,
    create_access_token,
    create_password_reset_token,
    create_user,
    get_current_user,
    get_user_by_email,
    get_valid_reset_token,
    reset_password_with_token,
    verify_password,
)

from app.services.email import build_reset_url, send_password_reset_email


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


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        create_user(
            db,
            username=data.username,
            email=data.email,
            password=data.password,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # Not auto-logged-in: the existing architecture issues JWTs only
    # from /login after real credential verification - reusing that
    # single code path (rather than also minting a token here) keeps
    # login the one place a session can start.
    return MessageResponse(
        detail="Account created successfully. Please log in.",
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
    "/change-password",
    response_model=MessageResponse,
    summary="Change the current user's password",
)
def change_password_endpoint(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(
        data.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    change_password(db, current_user, data.new_password)

    return MessageResponse(detail="Password changed successfully.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link",
)
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, data.email)

    # Same response whether or not the email exists - never reveals
    # account existence. Only real accounts (found) get an actual
    # token generated/sent.
    if user is not None and user.is_active:
        raw_token = create_password_reset_token(db, user)

        send_password_reset_email(
            user.email,
            build_reset_url(raw_token),
        )

    return MessageResponse(
        detail=(
            "If an account exists for this email, a password reset "
            "link has been sent."
        ),
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset a password using a reset token",
)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    reset_token = get_valid_reset_token(db, data.token)

    if reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    reset_password_with_token(db, reset_token, data.new_password)

    return MessageResponse(
        detail="Password reset successfully. You can now log in.",
    )


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
