# Test database setup

Tests run **only** against `armando_furniture_test`. `backend/tests/conftest.py`
sets `DATABASE_URL` from `TEST_DATABASE_URL` (read from `backend/.env.test`)
before importing the application, and aborts the run if the resolved database
name is not exactly `armando_furniture_test`.

## One-time setup

1. `psql -h 127.0.0.1 -p 5433 -U <user> -c "CREATE DATABASE armando_furniture_test"`
2. `cp backend/.env.test.example backend/.env.test` and fill in local credentials.
3. `cd backend && DATABASE_URL="<the test URL>" python -m alembic upgrade head`

## Running tests

`cd backend && python -m pytest`

No environment variables needed at the call site — `conftest.py` resolves them.

## After adding a migration

Re-run step 3 so the test database stays at head.

`backend/.env.test` is gitignored. Never point it at `armando_furniture`.

## Alembic's own guard

Migrations have the same isolation problem tests had, with one extra wrinkle:
`backend/.env`'s `DATABASE_URL` points at the development database, so a bare
`alembic` command used to resolve there silently. `backend/alembic/env.py` now
resolves and verifies the target *before* any migration DDL runs:

- With no `DATABASE_URL` set, it defaults to `TEST_DATABASE_URL` from
  `backend/.env.test` - the same file and variable the test suite uses.
- An explicit `DATABASE_URL` naming `armando_furniture_test` is accepted and
  takes priority over `backend/.env.test`.
- Every run prints the resolved database name to stderr, e.g.
  `[alembic] target database: armando_furniture_test`.
- Any other database name is refused with a `RuntimeError` - including
  `armando_furniture` itself.

Development migrations require an explicit, deliberate opt-in:

```
ALEMBIC_ALLOW_DEV_MIGRATION=1 DATABASE_URL="<the armando_furniture URL>" \
  python -m alembic upgrade head
```

The opt-in only authorizes `armando_furniture` specifically (not an arbitrary
URL), and prints a loud warning banner naming the development database before
proceeding.
