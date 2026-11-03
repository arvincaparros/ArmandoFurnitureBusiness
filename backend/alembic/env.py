from logging.config import fileConfig
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context


# Capture any DATABASE_URL a human exported deliberately BEFORE the
# `app.database.connection` import below runs. connection.py calls
# load_dotenv() itself at import time, so capturing this value any
# later could not tell "the operator exported this" apart from
# "backend/.env supplied the development URL". Capturing late would
# make the guard useless: a bare `alembic upgrade head` would resolve
# to the development database and then simply fail the allowlist
# check below, instead of correctly defaulting to the test database.
_preset_database_url = os.environ.get("DATABASE_URL")

from app.database.connection import Base  # noqa: E402
from app.database import models  # noqa: E402

from app.database.alembic_target import (  # noqa: E402
    DEV_OPT_IN_VAR,
    PRODUCTION_DATABASE_NAME_VAR,
    PRODUCTION_OPT_IN_VAR,
    resolve_migration_url,
)


_backend_dir = Path(__file__).resolve().parents[1]

# Read backend/.env.test's value directly via dotenv_values() rather
# than load_dotenv() + os.environ.get(): that sidesteps any ordering
# dependence on whatever connection.py's own load_dotenv() call
# already put into the process environment, and needs no relative
# path that would depend on the working directory `alembic` was
# invoked from.
_test_database_url = dotenv_values(
    _backend_dir / ".env.test",
).get("TEST_DATABASE_URL")

_allow_dev_migration = os.environ.get(DEV_OPT_IN_VAR) in (
    "1",
    "true",
    "TRUE",
    "yes",
)

_dev_database_url = None

if _allow_dev_migration:
    # Only read backend/.env (the development URL) when the opt-in is
    # active - it must never leak into the default resolution path.
    _dev_database_url = dotenv_values(
        _backend_dir / ".env",
    ).get("DATABASE_URL")

_allow_production_migration = os.environ.get(PRODUCTION_OPT_IN_VAR) in (
    "1",
    "true",
    "TRUE",
    "yes",
)

# Read directly from the real process environment, same as
# DATABASE_URL - there is no backend/.env file on the production
# platform to source this from.
_production_database_name = os.environ.get(PRODUCTION_DATABASE_NAME_VAR)

_resolved_url, _resolved_database_name = resolve_migration_url(
    preset_url=_preset_database_url,
    test_url=_test_database_url,
    dev_url=_dev_database_url,
    allow_dev=_allow_dev_migration,
    allow_production=_allow_production_migration,
    production_database_name=_production_database_name,
)

# Verify the effective target BEFORE any DDL executes: this module
# runs at import time, ahead of run_migrations_offline() /
# run_migrations_online() below, so the print below (and the
# RuntimeError above, if resolution failed) always happens first.
if _allow_dev_migration:
    print(
        "\n".join(
            [
                "",
                "!" * 70,
                "!! DEVELOPMENT MIGRATION OPT-IN ACTIVE",
                "!! This run will execute migration DDL against "
                f"'{_resolved_database_name}' - the DEVELOPMENT "
                "database.",
                "!! Ctrl+C now if this was not intentional.",
                "!" * 70,
                "",
            ]
        ),
        file=sys.stderr,
    )

if _allow_production_migration:
    print(
        "\n".join(
            [
                "",
                "!" * 70,
                "!! PRODUCTION MIGRATION OPT-IN ACTIVE",
                "!! This run will execute migration DDL against "
                f"'{_resolved_database_name}' - the PRODUCTION "
                "database.",
                "!! Ctrl+C now if this was not intentional.",
                "!" * 70,
                "",
            ]
        ),
        file=sys.stderr,
    )

print(
    f"[alembic] target database: {_resolved_database_name}",
    file=sys.stderr,
)


# Alembic Config object
config = context.config


# Configure Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


config.set_main_option(
    "sqlalchemy.url",
    _resolved_url,
)


# SQLAlchemy metadata for Alembic autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
