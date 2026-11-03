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

    # Generate the second plan FIRST, while capacity is still at its
    # original level, then top up before applying it.
    #
    # The order matters and is not arbitrary: /optimize is NOT
    # ledger-aware - it plans against the RAW CycleResource capacity,
    # so a plan generated after a 3x top-up asks for ~3x and can never
    # fit in (3x - what the first application already consumed).
    # Generating against 1x and then raising capacity to 3x leaves
    # 3x - 1x = 2x remaining for a plan that needs ~1x, which is the
    # real shop sequence: the plan is drawn up, then the materials are
    # bought, then production is committed.
    _optimize(client, optimization_cycle.id)

    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = (
            cycle_resource.available_quantity * Decimal("3")
        )

    db.commit()

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


def test_repeated_applies_succeed_without_fresh_capacity(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Approved business-rule change: Apply no longer rejects a plan for
    exceeding what's left of a resource's declared capacity after an
    earlier application this cycle. Test Labor sits exactly at its
    576 capacity after the first apply (see the comment on
    test_a_new_run_can_be_applied_in_the_same_cycle_and_accumulates),
    so a second, then a third, apply of the identical plan - with NO
    capacity ever added - must still succeed, each recording its own
    full-sized ledger entry rather than being blocked or silently
    reduced.
    """

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    _optimize(client, optimization_cycle.id)
    second = _apply(client, optimization_cycle.id)
    assert second.status_code == 200, second.text

    _optimize(client, optimization_cycle.id)
    third = _apply(client, optimization_cycle.id)
    assert third.status_code == 200, third.text

    applications = (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .order_by(ProductionApplication.id)
        .all()
    )

    assert len(applications) == 3

    # Every application recorded its own FULL, unreduced consumption -
    # none of the three was ever capped or offset against the others.
    for application in applications:
        labor_item = next(
            item for item in application.resource_items
            if item.resource_name == "Test Labor"
        )
        assert labor_item.consumed_quantity == Decimal("576.0000")


def test_resource_utilization_shows_true_over_allocation_after_repeated_applies(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Requirement 3 of the approved business-rule change: utilization
    reporting must show the TRUE, uncapped total after repeated
    applies - never capped at 100%, never reset, and
    remaining_quantity may go negative. Two applies of the same plan
    each consume Test Labor's full 576 capacity, for 1152 against a
    declared 576 - double its capacity - and the report must say so
    plainly rather than hide it.
    """

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    applications_response = client.get(
        f"/api/production-cycles/{optimization_cycle.id}/applications"
    )
    assert applications_response.status_code == 200
    assert len(applications_response.json()) == 2

    utilization_response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )
    assert utilization_response.status_code == 200

    labor = next(
        item
        for item in utilization_response.json()["resources"]
        if item["resource_name"] == "Test Labor"
    )

    assert Decimal(labor["consumed_quantity"]) == Decimal(
        "1152.0000"
    )
    assert Decimal(labor["available_quantity"]) == Decimal(
        "576.0000"
    )
    assert Decimal(labor["utilization_rate"]) == Decimal("200.00")
    assert Decimal(labor["remaining_quantity"]) == Decimal(
        "-576.0000"
    )
    assert labor["status"] == "bottleneck"


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

    # Second plan generated before the top-up - see the ordering note
    # in test_a_new_run_can_be_applied_in_the_same_cycle_and_accumulates.
    _optimize(client, optimization_cycle.id)

    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = (
            cycle_resource.available_quantity * Decimal("3")
        )

    db.commit()

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


def test_apply_succeeds_even_when_capacity_is_reduced_to_zero_after_generate(
    client, db, cleanup_applications, optimization_cycle,
    test_resources,
):
    """
    The approved business-rule change applies uniformly, not only to
    capacity already consumed by a prior application: a plan is still
    applied even if every resource's declared capacity is reduced to
    zero after it was generated. No fabricated capacity, no silent
    cap - the recorded consumption is the plan's real requirement, and
    remaining capacity is deeply negative, exactly as requirement 3
    describes.
    """

    from app.database.models import CycleResource

    first = _optimize(client, optimization_cycle.id)

    assert any(
        allocation["quantity"] > 0
        for allocation in first["allocations"]
    )

    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = Decimal("0")

    db.commit()

    response = _apply(client, optimization_cycle.id)

    assert response.status_code == 200, response.text

    application = db.query(ProductionApplication).filter(
        ProductionApplication.production_cycle_id
        == optimization_cycle.id
    ).one()

    labor_item = next(
        item for item in application.resource_items
        if item.resource_name == "Test Labor"
    )

    assert labor_item.consumed_quantity == Decimal("576.0000")

    utilization = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    ).json()

    labor_usage = next(
        item for item in utilization["resources"]
        if item["resource_name"] == "Test Labor"
    )

    assert Decimal(labor_usage["available_quantity"]) == Decimal("0")
    assert Decimal(labor_usage["remaining_quantity"]) == Decimal(
        "-576.0000"
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


# --- Restored: Generate is independent of previous Generate/Apply -----


def test_second_generate_in_the_same_cycle_matches_the_first_not_zero(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Generate is a proposal only - it must solve against the cycle's
    current declared resource capacities every time, independently of
    what an earlier application in this same cycle has already
    consumed. Calling /optimize again right after an Apply, with no
    capacity added, must reproduce the exact same proposal as the
    first call (the CBC solver is deterministic for unchanged inputs -
    see test_apply_optimization_rolls_back_on_mid_transaction_failure's
    own note on this) - never an all-zero plan just because the first
    application already spent part of this capacity.
    """

    first = _optimize(client, optimization_cycle.id)
    assert _apply(client, optimization_cycle.id).status_code == 200

    second = _optimize(client, optimization_cycle.id)

    first_by_product = {
        item["product_id"]: item["quantity"]
        for item in first["allocations"]
    }
    second_by_product = {
        item["product_id"]: item["quantity"]
        for item in second["allocations"]
    }

    assert second_by_product == first_by_product
    assert any(
        quantity > 0 for quantity in second_by_product.values()
    )


def test_repeated_generate_without_apply_writes_no_ledger_row_or_resource_change(
    client, db, cleanup_applications, optimization_cycle,
):
    """
    Generate is read-only: calling /optimize more than once, with no
    Apply in between, must never write a ProductionApplication row nor
    change any CycleResource's declared available_quantity.
    """

    from app.database.models import CycleResource

    original_quantities = {
        cycle_resource.resource_id: cycle_resource.available_quantity
        for cycle_resource in db.query(CycleResource).filter(
            CycleResource.production_cycle_id == optimization_cycle.id
        ).all()
    }

    _optimize(client, optimization_cycle.id)
    _optimize(client, optimization_cycle.id)
    _optimize(client, optimization_cycle.id)

    db.expire_all()

    current_quantities = {
        cycle_resource.resource_id: cycle_resource.available_quantity
        for cycle_resource in db.query(CycleResource).filter(
            CycleResource.production_cycle_id == optimization_cycle.id
        ).all()
    }

    assert current_quantities == original_quantities

    assert (
        db.query(ProductionApplication)
        .filter(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


def test_generate_preview_never_affects_available_stock(
    client, db, cleanup_applications, optimization_cycle, test_products,
):
    """
    Unapplied Generate results must never be counted as produced
    inventory - Available Stock is driven solely by the ledger
    (ProductionApplication), never by an OptimizationRun/
    OptimizationResult preview.
    """

    from app.services.inventory import get_available_stock

    before = get_available_stock(db)

    _optimize(client, optimization_cycle.id)
    _optimize(client, optimization_cycle.id)

    db.expire_all()

    after = get_available_stock(db)

    for product in test_products:
        assert after.get(
            product.id, Decimal("0")
        ) == before.get(
            product.id, Decimal("0")
        )
