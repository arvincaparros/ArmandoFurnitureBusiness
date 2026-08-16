from datetime import datetime, timedelta, timezone

import jwt
import pytest

from sqlalchemy.exc import IntegrityError

from app.database.models import PasswordResetToken, User

from app.services.auth import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    create_access_token,
    create_password_reset_token,
    hash_password,
    verify_password,
)


TEST_USERNAME = "test_auth_user"
TEST_EMAIL = "test_auth_user@example.com"
TEST_PASSWORD = "CorrectHorseBattery9!"

INACTIVE_USERNAME = "test_auth_inactive_user"
INACTIVE_EMAIL = "test_auth_inactive_user@example.com"
INACTIVE_PASSWORD = "AlsoAValidPassword9!"

DUPLICATE_USERNAME = "test_auth_duplicate_user"
DUPLICATE_EMAIL = "test_auth_duplicate_user@example.com"

REGISTER_USERNAME = "test_auth_register_user"
REGISTER_EMAIL = "test_auth_register_user@example.com"
REGISTER_PASSWORD = "RegisterPassword9!"


@pytest.fixture
def cleanup_test_users(db):
    usernames = [
        TEST_USERNAME,
        INACTIVE_USERNAME,
        DUPLICATE_USERNAME,
        REGISTER_USERNAME,
    ]

    db.query(User).filter(
        User.username.in_(usernames)
    ).delete(
        synchronize_session=False
    )

    db.commit()

    yield

    db.rollback()

    db.query(User).filter(
        User.username.in_(usernames)
    ).delete(
        synchronize_session=False
    )

    db.commit()


@pytest.fixture
def test_user(db, cleanup_test_users):
    user = User(
        username=TEST_USERNAME,
        email=TEST_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user


@pytest.fixture
def inactive_test_user(db, cleanup_test_users):
    user = User(
        username=INACTIVE_USERNAME,
        email=INACTIVE_EMAIL,
        password_hash=hash_password(INACTIVE_PASSWORD),
        is_active=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user


def _expired_token(user: User) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": now - timedelta(minutes=120),
        "exp": now - timedelta(minutes=60),
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


# ---------------------------------------------------------------
# Login
# ---------------------------------------------------------------

def test_login_success(client, test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert body["token_type"] == "bearer"


def test_login_invalid_username(client, test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "username": "no_such_user",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Incorrect username or password"
    )


def test_login_invalid_password(client, test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Incorrect username or password"
    )


def test_login_invalid_username_and_password_give_same_error(
    client,
    test_user,
):
    """
    The error for "no such user" and "wrong password" must be
    identical, so a caller can't use the response to enumerate
    valid usernames.
    """

    unknown_user_response = client.post(
        "/api/auth/login",
        json={
            "username": "no_such_user",
            "password": TEST_PASSWORD,
        },
    )

    wrong_password_response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": "wrong-password",
        },
    )

    assert (
        unknown_user_response.json()["detail"]
        == wrong_password_response.json()["detail"]
    )


def test_login_missing_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={},
    )

    assert response.status_code == 422


def test_login_inactive_user(client, inactive_test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "username": INACTIVE_USERNAME,
            "password": INACTIVE_PASSWORD,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


def test_login_response_does_not_expose_password_hash(
    client,
    test_user,
):
    response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert "password_hash" not in response.json()
    assert "password" not in response.json()


# ---------------------------------------------------------------
# Current user (/me)
# ---------------------------------------------------------------

def test_me_success(client, test_user):
    login_response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    token = login_response.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["username"] == TEST_USERNAME
    assert body["id"] == test_user.id
    assert body["is_active"] is True
    assert "created_at" in body


def test_me_response_does_not_expose_password_hash(
    client,
    test_user,
):
    login_response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    token = login_response.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "password_hash" not in response.json()
    assert set(response.json().keys()) == {
        "id",
        "username",
        "email",
        "is_active",
        "created_at",
    }


def test_me_missing_token(unauthenticated_client, test_user):
    response = unauthenticated_client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_invalid_token(client, test_user):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_me_expired_token(client, test_user):
    token = _expired_token(test_user)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_me_inactive_user_with_valid_token(
    client,
    db,
    inactive_test_user,
):
    """
    A token issued while the user was active must stop working the
    moment the account is deactivated - this is the mechanism that
    substitutes for token revocation in a stateless JWT design.
    """

    inactive_test_user.is_active = True
    db.commit()

    login_response = client.post(
        "/api/auth/login",
        json={
            "username": INACTIVE_USERNAME,
            "password": INACTIVE_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    inactive_test_user.is_active = False
    db.commit()

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"


# ---------------------------------------------------------------
# Logout
# ---------------------------------------------------------------

def test_logout_requires_authentication(unauthenticated_client):
    response = unauthenticated_client.post("/api/auth/logout")

    assert response.status_code == 401


def test_logout_success_with_valid_token(client, test_user):
    login_response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


# ---------------------------------------------------------------
# User model / password hashing (service + DB layer)
# ---------------------------------------------------------------

def test_duplicate_username_rejected_by_unique_constraint(
    db,
    cleanup_test_users,
):
    first = User(
        username=DUPLICATE_USERNAME,
        email=DUPLICATE_EMAIL,
        password_hash=hash_password("SomePassword9!"),
        is_active=True,
    )

    db.add(first)
    db.commit()

    duplicate = User(
        username=DUPLICATE_USERNAME,
        email="a-different-email@example.com",
        password_hash=hash_password("AnotherPassword9!"),
        is_active=True,
    )

    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_hash_password_does_not_store_plaintext():
    password_hash = hash_password(TEST_PASSWORD)

    assert password_hash != TEST_PASSWORD
    assert TEST_PASSWORD not in password_hash


def test_hash_password_is_salted():
    """Hashing the same password twice must not produce the same hash."""

    first_hash = hash_password(TEST_PASSWORD)
    second_hash = hash_password(TEST_PASSWORD)

    assert first_hash != second_hash
    assert verify_password(TEST_PASSWORD, first_hash) is True
    assert verify_password(TEST_PASSWORD, second_hash) is True


def test_verify_password_correct_and_incorrect():
    password_hash = hash_password(TEST_PASSWORD)

    assert verify_password(TEST_PASSWORD, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_create_access_token_contains_expected_claims(test_user):
    token = create_access_token(test_user)

    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
    )

    assert payload["sub"] == str(test_user.id)
    assert payload["username"] == test_user.username
    assert "exp" in payload
    assert "iat" in payload


# ---------------------------------------------------------------
# Registration
# ---------------------------------------------------------------

def test_register_success(client, cleanup_test_users, db):
    response = client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": REGISTER_EMAIL,
            "password": REGISTER_PASSWORD,
            "confirm_password": REGISTER_PASSWORD,
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "detail": "Account created successfully. Please log in."
    }

    created = (
        db.query(User)
        .filter(User.username == REGISTER_USERNAME)
        .first()
    )

    assert created is not None
    assert created.email == REGISTER_EMAIL


def test_register_does_not_auto_login(client, cleanup_test_users):
    """Registration returns a plain message, never an access_token."""

    response = client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": REGISTER_EMAIL,
            "password": REGISTER_PASSWORD,
            "confirm_password": REGISTER_PASSWORD,
        },
    )

    assert response.status_code == 201
    assert "access_token" not in response.json()


def test_register_password_is_hashed(client, cleanup_test_users, db):
    client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": REGISTER_EMAIL,
            "password": REGISTER_PASSWORD,
            "confirm_password": REGISTER_PASSWORD,
        },
    )

    created = (
        db.query(User)
        .filter(User.username == REGISTER_USERNAME)
        .first()
    )

    assert created.password_hash != REGISTER_PASSWORD
    assert verify_password(
        REGISTER_PASSWORD, created.password_hash
    ) is True


def test_register_duplicate_username_rejected(
    client, test_user, cleanup_test_users,
):
    response = client.post(
        "/api/auth/register",
        json={
            "username": TEST_USERNAME,
            "email": "someone-else@example.com",
            "password": REGISTER_PASSWORD,
            "confirm_password": REGISTER_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert "username" in response.json()["detail"].lower()


def test_register_duplicate_email_rejected(
    client, test_user, cleanup_test_users,
):
    response = client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": TEST_EMAIL,
            "password": REGISTER_PASSWORD,
            "confirm_password": REGISTER_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert "email" in response.json()["detail"].lower()


def test_register_invalid_email_rejected(client, cleanup_test_users):
    response = client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": "not-an-email",
            "password": REGISTER_PASSWORD,
            "confirm_password": REGISTER_PASSWORD,
        },
    )

    assert response.status_code == 422


def test_register_password_mismatch_rejected(client, cleanup_test_users):
    response = client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": REGISTER_EMAIL,
            "password": REGISTER_PASSWORD,
            "confirm_password": "SomethingElse9!",
        },
    )

    assert response.status_code == 422


def test_register_short_password_rejected(client, cleanup_test_users):
    response = client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": REGISTER_EMAIL,
            "password": "short1",
            "confirm_password": "short1",
        },
    )

    assert response.status_code == 422


def test_register_response_never_exposes_password(
    client, cleanup_test_users,
):
    response = client.post(
        "/api/auth/register",
        json={
            "username": REGISTER_USERNAME,
            "email": REGISTER_EMAIL,
            "password": REGISTER_PASSWORD,
            "confirm_password": REGISTER_PASSWORD,
        },
    )

    body = response.json()

    assert "password" not in body
    assert "password_hash" not in body


# ---------------------------------------------------------------
# Change password
# ---------------------------------------------------------------

def _login(client, username, password):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )

    return response.json()["access_token"]


def test_change_password_requires_authentication(
    unauthenticated_client,
):
    response = unauthenticated_client.post(
        "/api/auth/change-password",
        json={
            "current_password": "whatever",
            "new_password": "NewPassword9!",
            "confirm_password": "NewPassword9!",
        },
    )

    assert response.status_code == 401


def test_change_password_success(client, test_user, db):
    token = _login(client, TEST_USERNAME, TEST_PASSWORD)

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "BrandNewPassword9!",
            "confirm_password": "BrandNewPassword9!",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "detail": "Password changed successfully."
    }

    db.refresh(test_user)

    # New password hash is actually persisted...
    assert verify_password(
        "BrandNewPassword9!", test_user.password_hash
    ) is True

    # ...and the old password no longer works.
    assert verify_password(
        TEST_PASSWORD, test_user.password_hash
    ) is False


def test_change_password_new_password_actually_logs_in(
    client, test_user,
):
    token = _login(client, TEST_USERNAME, TEST_PASSWORD)

    client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "BrandNewPassword9!",
            "confirm_password": "BrandNewPassword9!",
        },
    )

    old_password_login = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": "BrandNewPassword9!",
        },
    )

    assert new_password_login.status_code == 200


def test_change_password_wrong_current_password_rejected(
    client, test_user,
):
    token = _login(client, TEST_USERNAME, TEST_PASSWORD)

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "wrong-current-password",
            "new_password": "BrandNewPassword9!",
            "confirm_password": "BrandNewPassword9!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Current password is incorrect"
    )


def test_change_password_mismatch_rejected(client, test_user):
    token = _login(client, TEST_USERNAME, TEST_PASSWORD)

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "BrandNewPassword9!",
            "confirm_password": "SomethingDifferent9!",
        },
    )

    assert response.status_code == 422


def test_change_password_same_as_current_rejected(client, test_user):
    token = _login(client, TEST_USERNAME, TEST_PASSWORD)

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": TEST_PASSWORD,
            "new_password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------------
# Forgot password / reset password
# ---------------------------------------------------------------

GENERIC_FORGOT_PASSWORD_MESSAGE = (
    "If an account exists for this email, a password reset "
    "link has been sent."
)


def test_forgot_password_unknown_email_returns_generic_response(
    client,
):
    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "no-such-account@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == (
        GENERIC_FORGOT_PASSWORD_MESSAGE
    )


def test_forgot_password_known_email_returns_same_generic_response(
    client, test_user,
):
    response = client.post(
        "/api/auth/forgot-password",
        json={"email": TEST_EMAIL},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == (
        GENERIC_FORGOT_PASSWORD_MESSAGE
    )


def test_forgot_password_known_email_creates_reset_token(
    client, test_user, db,
):
    client.post(
        "/api/auth/forgot-password",
        json={"email": TEST_EMAIL},
    )

    tokens = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == test_user.id)
        .all()
    )

    assert len(tokens) == 1
    assert tokens[0].used_at is None
    # Only a hash is stored - never the raw, usable token.
    assert tokens[0].token_hash != ""


def test_reset_password_success(client, test_user, db):
    raw_token = create_password_reset_token(db, test_user)

    response = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ResetPassword9!",
            "confirm_password": "ResetPassword9!",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "detail": "Password reset successfully. You can now log in."
    }

    db.refresh(test_user)

    assert verify_password(
        "ResetPassword9!", test_user.password_hash
    ) is True


def test_reset_password_new_password_actually_logs_in(
    client, test_user, db,
):
    raw_token = create_password_reset_token(db, test_user)

    client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ResetPassword9!",
            "confirm_password": "ResetPassword9!",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": "ResetPassword9!",
        },
    )

    assert response.status_code == 200


def test_reset_password_token_can_only_be_used_once(
    client, test_user, db,
):
    raw_token = create_password_reset_token(db, test_user)

    first_response = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ResetPassword9!",
            "confirm_password": "ResetPassword9!",
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "AnotherPassword9!",
            "confirm_password": "AnotherPassword9!",
        },
    )

    assert second_response.status_code == 400
    assert second_response.json()["detail"] == (
        "Invalid or expired reset token"
    )


def test_reset_password_expired_token_rejected(
    client, test_user, db,
):
    raw_token = create_password_reset_token(db, test_user)

    token_row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == test_user.id)
        .order_by(PasswordResetToken.id.desc())
        .first()
    )

    token_row.expires_at = datetime.now(timezone.utc) - timedelta(
        minutes=1
    )
    db.commit()

    response = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ResetPassword9!",
            "confirm_password": "ResetPassword9!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid or expired reset token"
    )


def test_reset_password_invalid_token_rejected(client):
    response = client.post(
        "/api/auth/reset-password",
        json={
            "token": "this-token-does-not-exist",
            "new_password": "ResetPassword9!",
            "confirm_password": "ResetPassword9!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid or expired reset token"
    )


def test_reset_password_mismatch_rejected(client, test_user, db):
    raw_token = create_password_reset_token(db, test_user)

    response = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ResetPassword9!",
            "confirm_password": "SomethingDifferent9!",
        },
    )

    assert response.status_code == 422
