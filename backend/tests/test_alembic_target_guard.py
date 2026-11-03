"""
Unit tests for the Alembic migration-target guard.

These tests exercise `resolve_migration_url` directly as a pure
function - no database, no environment mutation, no Alembic
invocation. The behavior that actually connects to a database (the
accepted dev-opt-in path, end to end) is deliberately NOT exercised
here or anywhere else: this suite proves the resolver's decisions are
correct in isolation, which is the only verification that is safe to
run without ever touching armando_furniture.
"""

import pytest

from app.database.alembic_target import (
    DEV_DATABASE_NAME,
    DEV_OPT_IN_VAR,
    PRODUCTION_DATABASE_NAME_VAR,
    PRODUCTION_OPT_IN_VAR,
    TEST_DATABASE_NAME,
    resolve_migration_url,
)


TEST_URL = f"postgresql://postgres:postgres@127.0.0.1:5433/{TEST_DATABASE_NAME}"
DEV_URL = f"postgresql://postgres:postgres@127.0.0.1:5433/{DEV_DATABASE_NAME}"
SCRATCH_URL = (
    "postgresql://postgres:postgres@127.0.0.1:5433/"
    "armando_furniture_scratch"
)
# Deliberately the SAME database name as DEV_URL, on a different host -
# this mirrors the real incident: Render's production database happens
# to be named identically to the local development convention. The
# production opt-in must still work correctly in exactly this case, and
# must remain fully independent of the dev opt-in.
PRODUCTION_URL = (
    f"postgresql://produser:fakeprodpass@render-prod-host:5432/"
    f"{DEV_DATABASE_NAME}"
)


def test_default_path_uses_test_url_when_no_preset_is_set():
    resolved_url, resolved_name = resolve_migration_url(
        preset_url=None,
        test_url=TEST_URL,
        dev_url=None,
        allow_dev=False,
    )

    assert resolved_url == TEST_URL
    assert resolved_name == TEST_DATABASE_NAME


def test_preset_url_naming_test_database_wins_over_test_url():
    other_test_url = (
        f"postgresql://postgres:postgres@127.0.0.1:5433/"
        f"{TEST_DATABASE_NAME}"
    )

    resolved_url, resolved_name = resolve_migration_url(
        preset_url=other_test_url,
        test_url=TEST_URL,
        dev_url=None,
        allow_dev=False,
    )

    assert resolved_url == other_test_url
    assert resolved_name == TEST_DATABASE_NAME


def test_preset_url_naming_dev_database_is_refused_without_opt_in():
    with pytest.raises(RuntimeError, match=DEV_OPT_IN_VAR):
        resolve_migration_url(
            preset_url=DEV_URL,
            test_url=TEST_URL,
            dev_url=None,
            allow_dev=False,
        )


def test_preset_url_naming_an_unrelated_database_is_refused():
    """
    Proves the allowlist is exact-match, not a "not the dev database"
    denylist: a database that is neither dev nor test must still be
    refused, even though it is real and reachable on this server.
    """

    with pytest.raises(RuntimeError, match="armando_furniture_scratch"):
        resolve_migration_url(
            preset_url=SCRATCH_URL,
            test_url=TEST_URL,
            dev_url=None,
            allow_dev=False,
        )


def test_no_preset_and_no_test_url_raises():
    with pytest.raises(RuntimeError, match="No migration target"):
        resolve_migration_url(
            preset_url=None,
            test_url=None,
            dev_url=None,
            allow_dev=False,
        )


def test_allow_dev_with_dev_url_resolves_to_dev_database():
    resolved_url, resolved_name = resolve_migration_url(
        preset_url=None,
        test_url=TEST_URL,
        dev_url=DEV_URL,
        allow_dev=True,
    )

    assert resolved_url == DEV_URL
    assert resolved_name == DEV_DATABASE_NAME


def test_allow_dev_without_dev_url_raises():
    with pytest.raises(RuntimeError, match=DEV_OPT_IN_VAR):
        resolve_migration_url(
            preset_url=None,
            test_url=TEST_URL,
            dev_url=None,
            allow_dev=True,
        )


def test_allow_dev_with_unrelated_dev_url_is_refused():
    """
    The opt-in authorizes the development database specifically, not
    a blanket bypass - a URL that is neither dev nor test must still
    be refused even with the opt-in active.
    """

    with pytest.raises(RuntimeError, match="armando_furniture_scratch"):
        resolve_migration_url(
            preset_url=None,
            test_url=TEST_URL,
            dev_url=SCRATCH_URL,
            allow_dev=True,
        )


def test_database_name_parsed_correctly_with_query_string():
    url_with_query = f"{TEST_URL}?sslmode=require"

    resolved_url, resolved_name = resolve_migration_url(
        preset_url=url_with_query,
        test_url=None,
        dev_url=None,
        allow_dev=False,
    )

    assert resolved_url == url_with_query
    assert resolved_name == TEST_DATABASE_NAME


def test_allow_production_with_matching_declared_name_resolves_to_preset_url():
    resolved_url, resolved_name = resolve_migration_url(
        preset_url=PRODUCTION_URL,
        test_url=TEST_URL,
        dev_url=None,
        allow_dev=False,
        allow_production=True,
        production_database_name=DEV_DATABASE_NAME,
    )

    assert resolved_url == PRODUCTION_URL
    assert resolved_name == DEV_DATABASE_NAME


def test_allow_production_without_declared_name_raises():
    with pytest.raises(RuntimeError, match=PRODUCTION_DATABASE_NAME_VAR):
        resolve_migration_url(
            preset_url=PRODUCTION_URL,
            test_url=TEST_URL,
            dev_url=None,
            allow_dev=False,
            allow_production=True,
            production_database_name=None,
        )


def test_allow_production_without_preset_url_raises():
    """
    Proves production migrations never silently fall back to the test
    database URL just because DATABASE_URL happens to be unset.
    """

    with pytest.raises(RuntimeError, match=PRODUCTION_OPT_IN_VAR):
        resolve_migration_url(
            preset_url=None,
            test_url=TEST_URL,
            dev_url=None,
            allow_dev=False,
            allow_production=True,
            production_database_name=DEV_DATABASE_NAME,
        )


def test_allow_production_with_mismatched_declared_name_is_refused():
    """
    The core "wrong database" catch: the operator's declared intent
    (production_database_name) and the actual DATABASE_URL target must
    agree, even though both are individually well-formed.
    """

    with pytest.raises(
        RuntimeError, match="armando_furniture_staging"
    ):
        resolve_migration_url(
            preset_url=PRODUCTION_URL,
            test_url=TEST_URL,
            dev_url=None,
            allow_dev=False,
            allow_production=True,
            production_database_name="armando_furniture_staging",
        )


def test_allow_production_cannot_target_test_database_name():
    """
    Even a self-consistent declaration (declared name matches the
    actual URL) must still be refused if that name is the reserved
    test database name - production must never be pointed at the
    disposable automated-test database.
    """

    with pytest.raises(RuntimeError, match=TEST_DATABASE_NAME):
        resolve_migration_url(
            preset_url=TEST_URL,
            test_url=TEST_URL,
            dev_url=None,
            allow_dev=False,
            allow_production=True,
            production_database_name=TEST_DATABASE_NAME,
        )


def test_allow_dev_and_allow_production_together_is_refused():
    """
    An ambiguous combination of opt-ins must raise rather than silently
    picking one - consistent with this module's "raise loudly rather
    than guess" design.
    """

    with pytest.raises(
        RuntimeError, match=f"{DEV_OPT_IN_VAR}.*{PRODUCTION_OPT_IN_VAR}"
    ):
        resolve_migration_url(
            preset_url=PRODUCTION_URL,
            test_url=TEST_URL,
            dev_url=DEV_URL,
            allow_dev=True,
            allow_production=True,
            production_database_name=DEV_DATABASE_NAME,
        )
