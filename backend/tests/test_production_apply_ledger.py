from decimal import Decimal

from app.database.models import (
    ProductionAllocation,
    ProductionApplication,
)
from app.services.production_application import (
    get_cycle_produced_by_product,
)


def _optimize(client, cycle_id):
    response = client.post(
        f"/api/production-cycles/{cycle_id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200, response.text

    return response.json()


def _apply(client, cycle_id):
    return client.post(
        f"/api/production-cycles/{cycle_id}/optimize/apply",
    )


def test_generating_a_plan_writes_no_ledger_row(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Requirement 1: generating an allocation must not increase
    inventory. Already true today (generate only writes
    OptimizationRun/OptimizationResult) - pinned here so a future
    change cannot quietly break it.
    """

    _optimize(client, optimization_cycle.id)

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


def test_apply_appends_a_ledger_row_with_product_and_resource_items(
    client, db, cleanup_applications, optimization_cycle,
):
    _optimize(client, optimization_cycle.id)

    assert _apply(client, optimization_cycle.id).status_code == 200

    applications = (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    assert len(applications) == 1

    application = applications[0]

    assert application.product_items, (
        "apply must record what it produced"
    )
    assert application.resource_items, (
        "apply must record the capacity it consumed"
    )
    assert all(
        item.quantity_produced > 0
        for item in application.product_items
    )


def test_applying_the_same_run_twice_is_rejected(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Without this, a double-click adds the same units twice and
    available stock is permanently wrong.
    """

    _optimize(client, optimization_cycle.id)

    assert _apply(client, optimization_cycle.id).status_code == 200

    second = _apply(client, optimization_cycle.id)

    assert second.status_code == 400
    assert "already been applied" in second.json()["detail"].lower()

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 1
    )


def test_a_new_run_can_be_applied_in_the_same_cycle_and_accumulates(
    client, db, cleanup_applications, optimization_cycle,
    test_resources,
):
    """
    The spec's Day-1/Day-5 scenario at the production level. The
    second apply needs fresh raw material (consumption is
    incremental), so capacity is topped up between applies - exactly
    what the shop does in reality.
    """

    from app.database.models import CycleResource

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    first_produced = get_cycle_produced_by_product(
        db, optimization_cycle.id,
    )

    assert first_produced

    # Top up capacity FIRST, then generate the second plan against it.
    #
    # The order matters and is not arbitrary: /optimize IS now
    # ledger-aware - it solves against what is actually LEFT of each
    # resource after the first apply (available_quantity minus
    # get_cycle_consumed_by_resource), not the cycle's full original
    # capacity. Topping up to 3x and THEN generating gives the second
    # plan (3x - what the first application already consumed) to work
    # with; generating before the top-up would size the plan to
    # whatever was left of the ORIGINAL 1x (near nothing, since the
    # first apply consumed most of it) and a later top-up could not
    # retroactively grow an already-generated, already-saved plan.
    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = (
            cycle_resource.available_quantity * Decimal("3")
        )

    db.commit()

    _optimize(client, optimization_cycle.id)

    assert _apply(client, optimization_cycle.id).status_code == 200

    db.expire_all()

    second_produced = get_cycle_produced_by_product(
        db, optimization_cycle.id,
    )

    for product_id, first_quantity in first_produced.items():
        assert second_produced[product_id] > first_quantity, (
            "the second application must ADD to the cycle's produced "
            "total, not replace it"
        )

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 2
    )


def test_a_second_apply_without_fresh_capacity_is_rejected(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Incremental consumption, enforced: with no capacity added, /optimize
    (now ledger-aware) correctly solves the second plan against what is
    actually LEFT after the first apply - near nothing - so it returns
    an all-zero plan rather than failing outright. Applying that empty
    plan must still be rejected (apply_optimization's pre-existing "no
    applicable product-level results" guard), never silently re-spending
    the first application's materials.
    """

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    _optimize(client, optimization_cycle.id)
    second = _apply(client, optimization_cycle.id)

    assert second.status_code == 400

    detail = second.json()["detail"].lower()

    assert "no applicable" in detail

    # Resource-specific explanation (Task: error message clarity):
    # Test Labor is the resource this fixture's products exhaust
    # first, and the message must name it and its unit, distinguish a
    # genuine capacity shortage from a minimum-demand conflict, and
    # tell the student what to do next.
    assert "test labor" in detail
    assert "0 hours remaining" in detail
    assert "not a minimum-demand conflict" in detail

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 1
    )


def test_production_allocation_still_holds_only_the_latest_plan(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    ProductionAllocation's contract is unchanged: one row per product,
    replaced wholesale on each apply. The LEDGER accumulates; the
    allocation does not. Pinned so a future change cannot blur the
    two.
    """

    from app.database.models import CycleResource

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    # Top up capacity BEFORE generating the second plan - see the
    # ordering note in
    # test_a_new_run_can_be_applied_in_the_same_cycle_and_accumulates.
    # /optimize is ledger-aware now, so the top-up has to happen first
    # or the generated plan sizes itself to near-nothing and a later
    # top-up cannot retroactively grow it.
    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = (
            cycle_resource.available_quantity * Decimal("3")
        )

    db.commit()

    _optimize(client, optimization_cycle.id)

    # Asserted, not fire-and-forget: if the second apply were rejected
    # the allocation rows would simply be the first apply's and the
    # one-row-per-product assertion below would pass vacuously.
    assert _apply(client, optimization_cycle.id).status_code == 200

    db.expire_all()

    allocations = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    product_ids = [row.product_id for row in allocations]

    assert len(product_ids) == len(set(product_ids)), (
        "ProductionAllocation must still be one row per product"
    )


def test_a_rejected_apply_leaves_no_ledger_row(
    client, db, cleanup_applications, optimization_cycle,
    test_resources,
):
    """
    Atomicity: a capacity rejection must not leave a half-written
    application behind, or stock would count units that were never
    produced.
    """

    from app.database.models import CycleResource

    _optimize(client, optimization_cycle.id)

    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = Decimal("0")

    db.commit()

    response = _apply(client, optimization_cycle.id)

    assert response.status_code == 400

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


def test_applications_endpoint_lists_the_ledger(
    client, db, cleanup_applications, optimization_cycle,
):
    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    response = client.get(
        f"/api/production-cycles/{optimization_cycle.id}/applications",
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["application_number"].startswith("PA-")
    assert payload[0]["product_items"]
    assert payload[0]["resource_items"]
