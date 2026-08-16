import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import PasswordResetToken, User


load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not configured")

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

RESET_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30")
)

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    statement = select(User).where(
        User.username == username
    )

    return db.scalars(statement).first()


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    statement = select(User).where(
        User.email == email
    )

    return db.scalars(statement).first()


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
) -> User:
    """
    Registers a new account. Raises ValueError (mapped to a 409 by
    the router) for a duplicate username or email - checked here
    rather than relying solely on the DB's unique constraints so the
    caller gets a specific, actionable message instead of a raw
    IntegrityError.
    """

    if get_user_by_username(db, username) is not None:
        raise ValueError("Username is already taken")

    if get_user_by_email(db, email) is not None:
        raise ValueError("Email is already registered")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    except Exception:
        db.rollback()
        raise


def change_password(
    db: Session,
    user: User,
    new_password: str,
) -> None:
    user.password_hash = hash_password(new_password)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _hash_reset_token(raw_token: str) -> str:
    # Same principle as password_hash: only a hash is ever persisted,
    # so a leaked table can't be used to reset anyone's password.
    # SHA-256 (not bcrypt) is appropriate here - the token itself is
    # already a long, high-entropy random value (unlike a
    # human-chosen password), so this only needs to be a fast,
    # collision-resistant lookup key, not a slow KDF.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_password_reset_token(
    db: Session,
    user: User,
) -> str:
    """
    Generates a cryptographically random reset token, stores only its
    hash + expiry, and returns the raw token to the caller (which is
    responsible for delivering it - e.g. via email - and must never
    persist or return it itself). Any previous unused tokens for this
    user are left in place; they simply become moot once a newer one
    is validated first, and all are single-use regardless.
    """

    raw_token = secrets.token_urlsafe(32)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )

    try:
        db.add(reset_token)
        db.commit()

        return raw_token

    except Exception:
        db.rollback()
        raise


def get_valid_reset_token(
    db: Session,
    raw_token: str,
) -> PasswordResetToken | None:
    """
    Resolves a raw token to its DB row only if it is both unused and
    unexpired - the two conditions that make a reset token usable at
    all. Returns None for a token that doesn't exist, was already
    used, or has expired, so the router can respond with one generic
    "invalid or expired" error without distinguishing which.
    """

    statement = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == _hash_reset_token(raw_token),
    )

    reset_token = db.scalars(statement).first()

    if reset_token is None:
        return None

    if reset_token.used_at is not None:
        return None

    expires_at = reset_token.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        return None

    return reset_token


def reset_password_with_token(
    db: Session,
    reset_token: PasswordResetToken,
    new_password: str,
) -> None:
    user = db.get(User, reset_token.user_id)

    if user is None:
        raise ValueError("Associated user no longer exists")

    user.password_hash = hash_password(new_password)
    reset_token.used_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User | None:
    """
    Resolves credentials to a User without regard to active status -
    callers decide how to handle an inactive account so that
    "wrong credentials" and "correct credentials, disabled account"
    can be reported differently where that distinction is wanted.
    """

    user = get_user_by_username(db, username)

    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": now,
        "exp": now + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    Reusable dependency for protecting an endpoint. Not applied to
    any business router yet - see Phase 1 scope notes in
    full-integration-authentication-audit.md.

    Re-checks is_active on every call (not just at login) because a
    stateless JWT cannot be revoked - this is the mechanism by which
    deactivating a user takes effect immediately, without waiting
    for that user's already-issued tokens to expire.
    """

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(
            credentials.credentials
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise unauthorized

    user_id = payload.get("sub")

    if user_id is None:
        raise unauthorized

    user = db.get(User, int(user_id))

    if user is None:
        raise unauthorized

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user
