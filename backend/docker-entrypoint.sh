#!/bin/sh
# Client-deployment entrypoint. Order matters:
#   1. wait for Postgres to accept connections
#   2. alembic upgrade head (schema only - never touches data)
#   3. seed ONLY if the database is genuinely empty (no Product rows) -
#      reset_demo_data() is intentionally never called here, so an
#      existing client's real data is never wiped by a container
#      restart/rebuild.
#   4. start uvicorn
set -e

echo "[entrypoint] Waiting for PostgreSQL..."
python -c "
import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

engine = create_engine(os.environ['DATABASE_URL'])

for attempt in range(30):
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        print('[entrypoint] Database is ready.')
        break
    except OperationalError:
        print(f'[entrypoint] Database not ready yet (attempt {attempt + 1}/30) - retrying in 2s...')
        time.sleep(2)
else:
    raise SystemExit('[entrypoint] Database did not become ready in time.')
"

echo "[entrypoint] Running Alembic migrations (schema only)..."
alembic upgrade head

echo "[entrypoint] Checking whether the database needs seeding..."
python -c "
from app.database.connection import SessionLocal
from app.database.models import Product
from app.database.seed import seed_database

db = SessionLocal()

try:
    existing_products = db.query(Product).count()
finally:
    db.close()

if existing_products == 0:
    print('[entrypoint] No existing products found - seeding client demo data...')
    seed_database()
    print('[entrypoint] Seed complete.')
else:
    print(f'[entrypoint] Found {existing_products} existing product(s) - skipping seed, existing data preserved.')
"

# Use PORT if the platform provides one (e.g. Koyeb), otherwise keep
# the existing default of 8000 (docker-compose.client.yml doesn't set
# PORT, so local Docker behavior is unchanged).
PORT="${PORT:-8000}"

echo "[entrypoint] Starting application server on port $PORT..."
exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
