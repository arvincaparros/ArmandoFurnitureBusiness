from datetime import datetime, timedelta, timezone

import jwt
import pytest

from sqlalchemy.exc import IntegrityError

from app.database.models import User

from app.services.auth import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)


TEST_USERNAME = "test_auth_user"
TEST_PASSWORD = "CorrectHorseBattery9!"

INACTIVE_USERNAME = "test_auth_inactive_user"
INACTIVE_PASSWORD = "AlsoAValidPassword9!"

DUPLICATE_USERNAME = "test_auth_duplicate_user"


@pytest.fixture
def cleanup_test_users(db):
    usernames = [
        TEST_USERNAME,
        INACTIVE_USERNAME,
        DUPLICATE_USERNAME,
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
        password_hash=hash_password("SomePassword9!"),
        is_active=True,
    )

    db.add(first)
    db.commit()

    duplicate = User(
        username=DUPLICATE_USERNAME,
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
