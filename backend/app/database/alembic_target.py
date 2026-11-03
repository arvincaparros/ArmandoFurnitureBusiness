"""
Pure resolver for which database Alembic migrations are allowed to
target.

Pulled out of backend/alembic/env.py so the resolution rules can be
unit-tested exhaustively with no database and no environment
mutation: env.py does all the I/O (reading os.environ, reading .env
files) and passes plain values in here. This module only decides, and
it decides by raising loudly rather than guessing whenever the result
would not be the single intended target - a silent fallback is
exactly how a migration ends up running against the wrong database.
"""

TEST_DATABASE_NAME = "armando_furniture_test"
DEV_DATABASE_NAME = "armando_furniture"
DEV_OPT_IN_VAR = "ALEMBIC_ALLOW_DEV_MIGRATION"
PRODUCTION_OPT_IN_VAR = "ALEMBIC_ALLOW_PRODUCTION_MIGRATION"
PRODUCTION_DATABASE_NAME_VAR = "ALEMBIC_PRODUCTION_DATABASE_NAME"


def _database_name(url: str) -> str:
    """
    Extract the database name from a connection URL: the final path
    segment, with any `?query` string stripped. Matches the approach
    backend/tests/conftest.py already uses for the equivalent pytest
    guard, so the two guards agree on what a URL's database name is.
    """

    return url.rsplit("/", 1)[-1].split("?")[0]


def resolve_migration_url(
    preset_url: str | None,
    test_url: str | None,
    dev_url: str | None,
    allow_dev: bool,
    allow_production: bool = False,
    production_database_name: str | None = None,
) -> tuple[str, str]:
    """
    Decide which database Alembic migrations may run against, and
    return (resolved_url, resolved_database_name).

    This is an exact-match allowlist, never a "not the dev database"
    denylist: a typo'd database name must abort the run rather than
    create a stray database or silently target something else. The
    `allow_dev` opt-in authorizes the development database
    specifically, not a blanket bypass for an arbitrary URL - so even
    with the opt-in active, `dev_url` is checked against
    DEV_DATABASE_NAME exactly as strictly as the default path checks
    its result against TEST_DATABASE_NAME.

    The production opt-in (`allow_production`) is independent of the
    development opt-in and carries its own confirmation: the operator
    must separately declare, via `production_database_name`
    (PRODUCTION_DATABASE_NAME_VAR), which database name they intend to
    target. That declared name is cross-checked against the database
    name `preset_url` (the real, platform-injected DATABASE_URL)
    actually resolves to - two independently-set values have to agree
    before any DDL runs. This catches both a missing opt-in AND a
    DATABASE_URL pointed somewhere the operator didn't intend, even
    with the opt-in active. There is no hardcoded production database
    name constant (unlike dev/test) because we don't control what the
    real hosting platform names it - so the declared name is the only
    anchor, and it is never allowed to equal TEST_DATABASE_NAME, which
    is reserved for the disposable automated-test database. Production
    never falls back to `test_url`: it must always resolve from the
    real `preset_url`.
    """

    if allow_dev and allow_production:
        raise RuntimeError(
            f"Both {DEV_OPT_IN_VAR} and {PRODUCTION_OPT_IN_VAR} are "
            "set. These opt-ins are mutually exclusive - unset "
            "whichever one does not apply to this run."
        )

    if allow_production:
        if not production_database_name:
            raise RuntimeError(
                f"{PRODUCTION_OPT_IN_VAR} is set, but "
                f"{PRODUCTION_DATABASE_NAME_VAR} was not. The "
                "production opt-in requires you to explicitly declare "
                "the database name you intend to target, so it can be "
                "checked against what DATABASE_URL actually resolves "
                "to."
            )

        if production_database_name == TEST_DATABASE_NAME:
            raise RuntimeError(
                f"{PRODUCTION_DATABASE_NAME_VAR} is set to "
                f"{TEST_DATABASE_NAME!r} - that name is reserved for "
                "the disposable automated-test database and must "
                "never be targeted by a production migration run."
            )

        if not preset_url:
            raise RuntimeError(
                f"{PRODUCTION_OPT_IN_VAR} is set, but no DATABASE_URL "
                "is present in the environment. Production migrations "
                "must resolve DATABASE_URL from the real platform "
                "environment, never from backend/.env.test."
            )

        resolved_name = _database_name(preset_url)

        if resolved_name != production_database_name:
            raise RuntimeError(
                f"{PRODUCTION_OPT_IN_VAR} is set, but DATABASE_URL "
                f"resolves to '{resolved_name}', which does not match "
                f"{PRODUCTION_DATABASE_NAME_VAR}="
                f"'{production_database_name}'. Refusing to run "
                "migrations until the declared target and the actual "
                "connection target agree."
            )

        return preset_url, resolved_name

    if allow_dev:
        if not dev_url:
            raise RuntimeError(
                f"{DEV_OPT_IN_VAR} is set, but no development "
                "database URL was supplied. Set DATABASE_URL to the "
                f"{DEV_DATABASE_NAME} connection string before "
                "running migrations with the development opt-in."
            )

        resolved_name = _database_name(dev_url)

        if resolved_name != DEV_DATABASE_NAME:
            raise RuntimeError(
                f"{DEV_OPT_IN_VAR} is set, but the supplied database "
                f"'{resolved_name}' is not {DEV_DATABASE_NAME}. The "
                "development opt-in authorizes the development "
                "database specifically, not an arbitrary URL - point "
                f"DATABASE_URL at {DEV_DATABASE_NAME}, or unset "
                f"{DEV_OPT_IN_VAR} to use the test database instead."
            )

        return dev_url, resolved_name

    resolved_url = preset_url or test_url

    if not resolved_url:
        raise RuntimeError(
            "No migration target is configured. Either set "
            "TEST_DATABASE_URL in backend/.env.test (see "
            "backend/.env.test.example), or deliberately opt in to "
            f"development migrations with {DEV_OPT_IN_VAR}=1 and "
            f"DATABASE_URL pointed at {DEV_DATABASE_NAME}."
        )

    resolved_name = _database_name(resolved_url)

    if resolved_name != TEST_DATABASE_NAME:
        raise RuntimeError(
            f"Refusing to run migrations against '{resolved_name}': "
            f"migrations default to {TEST_DATABASE_NAME} only. Point "
            "DATABASE_URL (or backend/.env.test's TEST_DATABASE_URL) "
            f"at {TEST_DATABASE_NAME}, or deliberately opt in to "
            f"development migrations with {DEV_OPT_IN_VAR}=1 and "
            f"DATABASE_URL set to {DEV_DATABASE_NAME}."
        )

    return resolved_url, resolved_name
