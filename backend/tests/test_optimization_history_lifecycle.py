"""
Regression coverage for the approved Optimization History cleanup:
every existing optimization run - including the old live plan (run
191) - is deleted and replaced by the eight authoritative Excel
records OP-164..OP-171.

The post-cleanup shape under test is:

- exactly eight summary-only records, all visible, no hidden row;
- zero OptimizationResult rows;
- the committed production allocation and resource utilization are
  untouched;
- Dashboard and Production Allocation keep working without the
  deleted run: the preview stays empty and Apply is rejected until a
  new plan is generated, while the committed allocation (and the
  frontend's financial-card fallback built on it, covered separately)
  keeps showing real production data;
- the next normal /optimize run is saved, visible, and becomes the
  first history row.

Every test builds this shape on its OWN fixture cycle (2026-08-09,
created and removed by conftest), never the real production cycle -
so the suite is safe to run against the scratch copy of the target
database.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from app.database.models import (
    OptimizationResult,
    OptimizationRun,
    ProductionAllocation,
    ResourceUtilizationRun,
)
from app.services.optimization_history import get_latest_optimal_run


# (started_at, duration_ms, total_profit, total_cost, products_produced)
# - the authoritative spreadsheet figures, so the eight records this
# test creates have exactly the shape the real import produces.
IMPORTED_RUNS = [
    (
        datetime(2026, 8, 16, 15, 40, 18),
        599400,
        Decimal("102236.8100"),
        Decimal("126162.8400"),
        40,
    ),
    (
        datetime(2026, 8, 23, 15, 25, 11),
        592200,
        Decimal("86390.3200"),
        Decimal("105109.3900"),
        31,
    ),
    (
        datetime(2026, 8, 30, 15, 1, 43),
        589800,
        Decimal("120515.7700"),
        Decimal("139383.8700"),
        43,
    ),
    (
        datetime(2026, 9, 6, 15, 32, 9),
        597000,
        Decimal("121329.1600"),
        Decimal("138570.4700"),
        45,
    ),
    (
        datetime(2026, 9, 13, 15, 4, 17),
        595800,
        Decimal("88424.0700"),
        Decimal("118975.6200"),
        34,
    ),
    (
        datetime(2026, 9, 20, 15, 50, 36),
        594000,
        Decimal("86390.3200"),
        Decimal("105109.3900"),
        21,
    ),
    (
        datetime(2026, 9, 27, 15, 30, 15),
        598200,
        Decimal("89528.4200"),
        Decimal("123406.2300"),
        30,
    ),
    (
        datetime(2026, 10, 4, 15, 45, 13),
        607200,
        Decimal("100490.5000"),
        Decimal("131383.2500"),
        31,
    ),
]


def _optimize(client, cycle_id):
    """
    A normal optimization run - the same request the Production
    Allocation page sends, which is what must keep appending history
    after the import.
    """

    response = client.post(
        f"/api/production-cycles/{cycle_id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200

    return response.json()


def _apply(client, cycle_id):
    return client.post(
        f"/api/production-cycles/{cycle_id}/optimize/apply",
    )


def _history(client, cycle_id, include_hidden=False):
    params = {"cycle_id": cycle_id}

    if include_hidden:
        params["include_hidden"] = True

    response = client.get(
        "/api/optimization/history",
        params=params,
    )

    assert response.status_code == 200

    return response.json()


def _delete_all_runs(db, cycle_id):
    """
    The DELETE half of the cleanup transaction, scoped to this test's
    own fixture cycle: every OptimizationResult belonging to the
    cycle's runs, then every run itself. Allocations and utilization
    snapshots are deliberately not touched - that is exactly what the
    target transaction promises to preserve.
    """

    db.expire_all()

    run_ids = [
        run_id
        for (run_id,) in db.query(OptimizationRun.id)
        .filter(
            OptimizationRun.production_cycle_id == cycle_id
        )
        .all()
    ]

    if run_ids:
        db.query(OptimizationResult).filter(
            OptimizationResult.optimization_run_id.in_(run_ids)
        ).delete(synchronize_session=False)

    db.query(OptimizationRun).filter(
        OptimizationRun.production_cycle_id == cycle_id
    ).delete(synchronize_session=False)

    db.commit()


def _insert_imported_records(db, cycle_id):
    """
    The eight Excel rows: aggregate figures only, no invented
    per-product results, completed_at derived from started_at plus the
    spreadsheet's seconds converted to integer milliseconds.
    """

    runs = []

    for (
        started_at,
        duration_ms,
        total_profit,
        total_cost,
        products_produced,
    ) in IMPORTED_RUNS:
        run = OptimizationRun(
            production_cycle_id=cycle_id,
            started_at=started_at,
            completed_at=started_at
            + timedelta(milliseconds=duration_ms),
            duration_ms=duration_ms,
            status="OPTIMAL",
            objective_value=total_profit,
            total_profit=total_profit,
            total_cost=total_cost,
            products_produced=products_produced,
            is_history_visible=True,
            is_summary_only=True,
        )

        db.add(run)
        runs.append(run)

    db.commit()

    for run in runs:
        db.refresh(run)

    return runs


def _build_cleanup_state(client, db, cycle_id):
    """
    Reproduce the approved cleanup on the fixture cycle: first commit
    a real plan (so there is production data to preserve), then
    delete every run and result and insert the eight Excel rows -
    what the target transaction does, minus the other cycles' data.
    """

    _optimize(client, cycle_id)

    apply_response = _apply(client, cycle_id)

    assert apply_response.status_code == 200

    _delete_all_runs(db, cycle_id)

    return _insert_imported_records(db, cycle_id)


def _allocation_snapshot(db, cycle_id):
    db.expire_all()

    return sorted(
        (allocation.product_id, allocation.quantity)
        for allocation in db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id
            == cycle_id
        )
        .all()
    )


def _utilization_run_ids(db, cycle_id):
    db.expire_all()

    return sorted(
        run_id
        for (run_id,) in db.query(ResourceUtilizationRun.id)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == cycle_id
        )
        .all()
    )


def _cleanup_cycle(db, cycle_id):
    """
    Remove everything these tests created for their own fixture cycle,
    in FK order, so the shared database is left exactly as found.
    """

    db.expire_all()

    db.query(ProductionAllocation).filter(
        ProductionAllocation.production_cycle_id == cycle_id
    ).delete(synchronize_session=False)

    db.query(ResourceUtilizationRun).filter(
        ResourceUtilizationRun.production_cycle_id == cycle_id
    ).delete(synchronize_session=False)

    db.query(OptimizationRun).filter(
        OptimizationRun.production_cycle_id == cycle_id
    ).delete(synchronize_session=False)

    db.commit()


def test_default_history_returns_exactly_the_eight_imported_records(
    client,
    db,
    optimization_cycle,
):
    """
    Requirement: after cleanup the History page shows exactly the
    eight student records, and no hidden row remains anywhere - the
    old live plan is physically deleted, not merely filtered.
    """

    imported = _build_cleanup_state(
        client,
        db,
        optimization_cycle.id,
    )

    imported_ids = [run.id for run in imported]

    try:
        history = _history(client, optimization_cycle.id)

        assert len(history) == 8

        # Newest first, exactly the eight imported rows.
        assert [entry["id"] for entry in history] == list(
            reversed(imported_ids)
        )

        assert all(
            entry["is_summary_only"] for entry in history
        )
        assert all(entry["results"] == [] for entry in history)

        assert [
            entry["products_produced"] for entry in history
        ] == [31, 30, 21, 34, 45, 43, 31, 40]

        # The Excel figures survive the round trip unchanged.
        newest = history[0]

        assert newest["started_at"].startswith(
            "2026-10-04T15:45:13"
        )
        assert newest["duration_ms"] == 607200
        assert newest["status"] == "OPTIMAL"
        assert newest["objective_value"] == "100490.5000"
        assert newest["total_profit"] == "100490.5000"
        assert newest["total_cost"] == "131383.2500"

        oldest = history[-1]

        assert oldest["started_at"].startswith(
            "2026-08-16T15:40:18"
        )
        assert oldest["duration_ms"] == 599400

        # include_hidden exposes nothing extra: run 191's counterpart
        # is gone, so both reads return the same eight rows.
        full = _history(
            client,
            optimization_cycle.id,
            include_hidden=True,
        )

        assert [entry["id"] for entry in full] == [
            entry["id"] for entry in history
        ]

        db.expire_all()

        assert (
            db.query(OptimizationRun)
            .filter(
                OptimizationRun.production_cycle_id
                == optimization_cycle.id
            )
            .count()
            == 8
        )

        assert (
            db.query(OptimizationResult)
            .filter(
                OptimizationResult.optimization_run_id.in_(
                    imported_ids
                )
            )
            .count()
            == 0
        )

    finally:
        _cleanup_cycle(db, optimization_cycle.id)


def test_cleanup_preserves_committed_production_data(
    client,
    db,
    optimization_cycle,
):
    """
    Requirement: Resources, Production Data Management and every
    existing production allocation survive the cleanup. The Dashboard
    summary honestly reports no usable run, while the committed
    allocation is still served (priced) to the two pages that read it.
    """

    _optimize(client, optimization_cycle.id)

    assert _apply(client, optimization_cycle.id).status_code == 200

    allocations_before = _allocation_snapshot(
        db,
        optimization_cycle.id,
    )
    utilization_before = _utilization_run_ids(
        db,
        optimization_cycle.id,
    )

    assert allocations_before
    assert utilization_before

    _delete_all_runs(db, optimization_cycle.id)
    _insert_imported_records(db, optimization_cycle.id)

    try:
        assert (
            _allocation_snapshot(db, optimization_cycle.id)
            == allocations_before
        )
        assert (
            _utilization_run_ids(db, optimization_cycle.id)
            == utilization_before
        )

        response = client.get(
            f"/api/production-cycles/"
            f"{optimization_cycle.id}/allocations"
        )

        assert response.status_code == 200

        rows = response.json()

        assert len(rows) == len(allocations_before)
        assert sum(
            Decimal(row["quantity"]) for row in rows
        ) == sum(quantity for _, quantity in allocations_before)

        # Revenue is always priceable from current cycle data; the
        # frontend's fallback sums exactly these rows.
        assert all(
            row["total_revenue"] is not None for row in rows
        )

        # The fixture cycle is the canonical latest (created just
        # now), so the dashboard summary is looking at the cycle whose
        # runs were just deleted.
        summary_response = client.get("/api/dashboard/summary")

        assert summary_response.status_code == 200
        assert (
            summary_response.json()["latest_optimization_profit"]
            is None
        )

    finally:
        _cleanup_cycle(db, optimization_cycle.id)


def test_new_native_run_is_saved_and_shown_after_cleanup(
    client,
    db,
    optimization_cycle,
):
    """
    Requirement: history must not stay capped at eight records. A
    normal optimization run generated after the cleanup is visible by
    default, becomes the newest row, and is what the dashboard reads.
    """

    imported = _build_cleanup_state(
        client,
        db,
        optimization_cycle.id,
    )

    imported_ids = [run.id for run in imported]

    try:
        assert len(_history(client, optimization_cycle.id)) == 8

        # The same action the Production Allocation page performs.
        _optimize(client, optimization_cycle.id)

        db.expire_all()

        new_run = (
            db.query(OptimizationRun)
            .filter(
                OptimizationRun.production_cycle_id
                == optimization_cycle.id
            )
            .order_by(OptimizationRun.id.desc())
            .first()
        )

        assert new_run.id not in imported_ids
        assert new_run.is_history_visible is True
        assert new_run.is_summary_only is False
        assert len(new_run.results) == 3

        # A native run stores the same total its own results add up
        # to, so the page's Products Produced column stays accurate.
        assert new_run.products_produced == int(
            sum(
                result.recommended_quantity
                for result in new_run.results
            )
        )

        history = _history(client, optimization_cycle.id)

        assert len(history) == 9
        assert history[0]["id"] == new_run.id
        assert history[0]["is_summary_only"] is False
        assert len(history[0]["results"]) == 3

        # The eight imported records are all still there.
        assert {entry["id"] for entry in history[1:]} == set(
            imported_ids
        )

        # The new run is not hidden, so both reads agree.
        full = _history(
            client,
            optimization_cycle.id,
            include_hidden=True,
        )

        assert [entry["id"] for entry in full] == [
            entry["id"] for entry in history
        ]

        assert (
            get_latest_optimal_run(db, optimization_cycle.id).id
            == new_run.id
        )

        summary_response = client.get("/api/dashboard/summary")

        assert summary_response.status_code == 200
        assert Decimal(
            summary_response.json()["latest_optimization_profit"]
        ) == new_run.total_profit

    finally:
        _cleanup_cycle(db, optimization_cycle.id)


def test_summary_only_records_are_never_selected_or_applied(
    client,
    db,
    optimization_cycle,
):
    """
    Requirement: imported records are excluded from production-plan
    selection and cannot be applied - even now that they are the only
    runs left. Apply must reject the newest one instead of falling
    back to some other plan behind the user's back, and the committed
    allocation must survive the rejected attempt untouched.
    """

    imported = _build_cleanup_state(
        client,
        db,
        optimization_cycle.id,
    )

    imported_ids = [run.id for run in imported]

    allocations_before = _allocation_snapshot(
        db,
        optimization_cycle.id,
    )
    utilization_before = _utilization_run_ids(
        db,
        optimization_cycle.id,
    )

    try:
        # Dashboard selection: no run qualifies as a usable plan.
        assert (
            get_latest_optimal_run(db, optimization_cycle.id)
            is None
        )

        history = _history(client, optimization_cycle.id)

        assert history[0]["id"] == imported_ids[-1]
        assert all(
            entry["is_summary_only"] for entry in history
        )
        assert all(entry["results"] == [] for entry in history)

        # What the frontend's findLatestOptimalRun reduces the list
        # to: nothing previewable, so Apply stays disabled.
        assert [
            entry
            for entry in history
            if entry["status"] == "OPTIMAL"
            and not entry["is_summary_only"]
            and entry["results"]
        ] == []

        response = _apply(client, optimization_cycle.id)

        assert response.status_code == 400

        assert response.json()["detail"] == (
            "This optimization record is summary-only and cannot be "
            "applied. Generate a new production plan instead."
        )

        # The committed allocation and its utilization snapshot were
        # not silently cleared by the rejected apply.
        assert (
            _allocation_snapshot(db, optimization_cycle.id)
            == allocations_before
        )
        assert (
            _utilization_run_ids(db, optimization_cycle.id)
            == utilization_before
        )

    finally:
        _cleanup_cycle(db, optimization_cycle.id)


def test_generate_then_apply_restores_the_production_workflow(
    client,
    db,
    optimization_cycle,
):
    """
    Requirement: the production workflow must keep working correctly
    without retaining the old run. After cleanup, Generate produces a
    new plan and Apply commits it, replacing the preserved allocation
    and adding a new utilization snapshot.
    """

    _build_cleanup_state(
        client,
        db,
        optimization_cycle.id,
    )

    try:
        # The cleanup left the previously applied plan in place.
        assert _allocation_snapshot(db, optimization_cycle.id)

        utilization_before = _utilization_run_ids(
            db,
            optimization_cycle.id,
        )

        _optimize(client, optimization_cycle.id)

        db.expire_all()

        new_run = (
            db.query(OptimizationRun)
            .filter(
                OptimizationRun.production_cycle_id
                == optimization_cycle.id
            )
            .order_by(OptimizationRun.id.desc())
            .first()
        )

        expected_allocations = {
            result.product_id: int(result.recommended_quantity)
            for result in new_run.results
            if int(result.recommended_quantity) > 0
        }

        response = _apply(client, optimization_cycle.id)

        assert response.status_code == 200

        assert (
            dict(
                _allocation_snapshot(db, optimization_cycle.id)
            )
            == expected_allocations
        )

        assert len(
            _utilization_run_ids(db, optimization_cycle.id)
        ) == len(utilization_before) + 1

        # Applying writes production state only - never history.
        assert len(_history(client, optimization_cycle.id)) == 9

    finally:
        _cleanup_cycle(db, optimization_cycle.id)
