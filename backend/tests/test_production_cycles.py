"""
Tests for the canonical "latest production cycle" resolution
(GET /api/production-cycles/latest and
app.services.production.get_latest_production_cycle).

The shared development database already has real, persistent
ProductionCycle rows (and cascading CycleResource/OptimizationRun/
ProductionAllocation data other phases depend on) - see
backend/docs/ for the audit that established this rule. Test design
here deliberately avoids ever deleting or committing changes against
that real data:

- The two positive-case tests ADD temporary rows with created_at
  timestamps shifted far into the future, so they are guaranteed to
  outrank any pre-existing real cycle regardless of what it is -
  this avoids needing to know or touch existing data at all. Cleaned
  up in a finally block, mirroring the rest of this test suite's
  fixture pattern.
- The empty-table case is tested at the service-function level
  (calling get_latest_production_cycle(db) directly, not via the
  HTTP client) using an uncommitted delete followed by db.rollback().
  This was a deliberate choice: the HTTP client uses a separate DB
  connection/session per request (via the get_db dependency), which
  cannot see an uncommitted delete made by the test's own session -
  so testing the 404 through the actual endpoint would require
  actually committing the deletion of all cycles (and their cascaded
  children) and restoring them afterward, which is unacceptably
  risky against shared real data. Testing the service function
  directly, with a delete that is never committed, achieves the same
  verification with zero risk: the database is provably unaffected
  since nothing is ever committed before the rollback.
"""

from datetime import datetime, timedelta

from app.database.models import ProductionCycle
from app.services.production import get_latest_production_cycle


def test_latest_cycle_returns_newest_created_at(client, db):
    # Shifted a year into the future so this is guaranteed to outrank
    # any pre-existing real cycle, whatever its created_at is.
    base = datetime.utcnow() + timedelta(days=365)

    older = ProductionCycle(
        cycle_date=datetime(2027, 1, 1),
        start_date=datetime(2027, 1, 1),
        end_date=datetime(2027, 1, 1),
        status="OPEN",
        created_at=base,
    )

    newer = ProductionCycle(
        cycle_date=datetime(2027, 1, 2),
        start_date=datetime(2027, 1, 2),
        end_date=datetime(2027, 1, 2),
        status="OPEN",
        created_at=base + timedelta(hours=1),
    )

    db.add_all([older, newer])
    db.commit()
    db.refresh(older)
    db.refresh(newer)

    try:
        response = client.get("/api/production-cycles/latest")

        assert response.status_code == 200
        assert response.json()["id"] == newer.id

    finally:
        db.delete(older)
        db.delete(newer)
        db.commit()


def test_latest_cycle_ties_break_on_highest_id(client, db):
    base = datetime.utcnow() + timedelta(days=366)

    first = ProductionCycle(
        cycle_date=datetime(2027, 2, 1),
        start_date=datetime(2027, 2, 1),
        end_date=datetime(2027, 2, 1),
        status="OPEN",
        created_at=base,
    )

    second = ProductionCycle(
        cycle_date=datetime(2027, 2, 2),
        start_date=datetime(2027, 2, 2),
        end_date=datetime(2027, 2, 2),
        status="OPEN",
        # Identical created_at - only the id tiebreaker should
        # decide which one is "latest".
        created_at=base,
    )

    db.add_all([first, second])
    db.commit()
    db.refresh(first)
    db.refresh(second)

    assert second.id > first.id, (
        "test assumes sequential id allocation for two rows "
        "inserted in the same commit"
    )

    try:
        response = client.get("/api/production-cycles/latest")

        assert response.status_code == 200
        assert response.json()["id"] == second.id

    finally:
        db.delete(first)
        db.delete(second)
        db.commit()


def test_latest_cycle_service_returns_none_when_no_cycles_exist(db):
    db.query(ProductionCycle).delete(synchronize_session=False)

    try:
        assert get_latest_production_cycle(db) is None
    finally:
        # Never committed - the shared database is unaffected.
        db.rollback()


def test_latest_cycle_endpoint_requires_authentication(
    unauthenticated_client,
):
    response = unauthenticated_client.get(
        "/api/production-cycles/latest"
    )

    assert response.status_code == 401


def test_specific_cycle_lookup_still_works_after_latest_route_added(
    client,
):
    """
    Guards against the exact route-ordering hazard this feature was
    warned about: GET /{cycle_id} must still work correctly for a
    numeric id, and an unknown numeric id must still 404 (not be
    swallowed by the new /latest route).
    """

    response = client.get("/api/production-cycles/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Production cycle not found"
