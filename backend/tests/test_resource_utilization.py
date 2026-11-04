from datetime import datetime, timezone
from decimal import Decimal

from app.database.models import (
    CycleResource,
    OptimizationResult,
    OptimizationRun,
    ProductionAllocation,
    ProductionCycle,
    Resource,
)
from app.services.resource_utilization import classify_utilization_status


def _allocate(db, cycle_id, product_id, quantity):
    allocation = ProductionAllocation(
        production_cycle_id=cycle_id,
        product_id=product_id,
        quantity=quantity,
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    return allocation


def test_utilization_with_no_allocations_reports_zero_consumption(
    client,
    optimization_cycle,
):
    response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["cycle_id"] == optimization_cycle.id
    assert len(data["resources"]) == 4
    assert data["bottlenecks"] == []
    assert Decimal(data["overall_utilization_rate"]) == Decimal("0.00")

    # No applied allocation: every resource is "normal", nothing is
    # at-risk, and the most-constrained resource is still reported
    # (0% utilization, but a real resource - not None) since resources
    # exist even though none has been consumed yet.
    assert data["at_risk_resources"] == []
    assert data["most_constrained_resource"] is not None
    assert Decimal(
        data["most_constrained_resource"]["utilization_rate"]
    ) == Decimal("0.00")
    assert data["material_resource_count"] == 3

    for item in data["resources"]:
        assert Decimal(item["consumed_quantity"]) == Decimal("0")
        assert Decimal(item["remaining_quantity"]) == Decimal(
            item["available_quantity"]
        )
        assert Decimal(item["utilization_rate"]) == Decimal("0.00")
        assert item["status"] == "normal"


def test_utilization_reflects_actual_allocation_consumption(
    client,
    db,
    optimization_cycle,
    test_products,
):
    products = {product.name: product for product in test_products}

    allocation = _allocate(
        db,
        optimization_cycle.id,
        products["Test Chair"].id,
        Decimal("17"),
    )

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        assert response.status_code == 200

        data = response.json()

        by_name = {
            item["resource_name"]: item
            for item in data["resources"]
        }

        expected_consumed = {
            "Test Wood": Decimal("204"),
            "Test Epoxy": Decimal("8.5"),
            "Test Nails": Decimal("2.55"),
            "Test Labor": Decimal("136"),
        }

        for name, expected_quantity in expected_consumed.items():
            item = by_name[name]

            assert Decimal(item["consumed_quantity"]) == expected_quantity

            available = Decimal(item["available_quantity"])
            remaining = Decimal(item["remaining_quantity"])

            assert remaining == available - expected_quantity

            if available > 0:
                expected_rate = (
                    expected_quantity / available * Decimal("100")
                ).quantize(Decimal("0.01"))

                assert Decimal(item["utilization_rate"]) == expected_rate

        # Epoxy capacity is 8, consumption is 8.5 -> over capacity.
        bottleneck_names = {
            bottleneck["resource_name"]
            for bottleneck in data["bottlenecks"]
        }

        assert bottleneck_names == {"Test Epoxy"}

        epoxy_bottleneck = next(
            bottleneck
            for bottleneck in data["bottlenecks"]
            if bottleneck["resource_name"] == "Test Epoxy"
        )

        assert Decimal(
            epoxy_bottleneck["shortage_quantity"]
        ) == Decimal("0.5")
        assert epoxy_bottleneck["is_binding"] is False

        # Labor and machine classification (resource_type based).
        assert Decimal(data["total_labor_hours_used"]) == Decimal("136")
        assert Decimal(
            data["total_labor_hours_capacity"]
        ) == Decimal("576")
        assert Decimal(data["total_machine_hours_used"]) == Decimal("0")
        assert Decimal(
            data["total_machine_hours_capacity"]
        ) == Decimal("0")

        expected_raw_materials = (
            expected_consumed["Test Wood"]
            + expected_consumed["Test Epoxy"]
            + expected_consumed["Test Nails"]
        )

        assert Decimal(
            data["total_raw_materials_consumed"]
        ) == expected_raw_materials

        # Overall rate is self-consistent with the returned totals.
        total_consumed = sum(
            Decimal(item["consumed_quantity"])
            for item in data["resources"]
        )
        total_available = sum(
            Decimal(item["available_quantity"])
            for item in data["resources"]
        )
        expected_overall_rate = (
            total_consumed / total_available * Decimal("100")
        ).quantize(Decimal("0.01"))

        assert Decimal(
            data["overall_utilization_rate"]
        ) == expected_overall_rate

    finally:
        db.delete(allocation)
        db.commit()


def test_utilization_unknown_cycle_returns_404(client):
    response = client.get("/api/resource-utilization/999999")

    assert response.status_code == 404


def test_utilization_default_route_uses_latest_cycle(
    client,
    db,
    optimization_cycle,
):
    newer_cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 10),
        start_date=datetime(2026, 8, 10),
        end_date=datetime(2026, 8, 10),
        status="OPEN",
    )
    db.add(newer_cycle)
    db.commit()
    db.refresh(newer_cycle)

    try:
        response = client.get("/api/resource-utilization")

        assert response.status_code == 200

        data = response.json()

        assert data["cycle_id"] == newer_cycle.id
        assert data["resources"] == []
        assert data["bottlenecks"] == []

    finally:
        db.delete(newer_cycle)
        db.commit()


def test_classify_utilization_status_thresholds():
    """
    Pure boundary test for the four-tier status classification -
    normal < 80, high 80-<90, at_risk 90-<100, bottleneck >= 100.
    """

    assert classify_utilization_status(Decimal("0")) == "normal"
    assert classify_utilization_status(Decimal("79.99")) == "normal"
    assert classify_utilization_status(Decimal("80")) == "high"
    assert classify_utilization_status(Decimal("89.99")) == "high"
    assert classify_utilization_status(Decimal("90")) == "at_risk"
    assert classify_utilization_status(Decimal("99.99")) == "at_risk"
    assert classify_utilization_status(Decimal("100")) == "bottleneck"
    assert classify_utilization_status(Decimal("150")) == "bottleneck"


def test_utilization_labor_at_99_percent_is_at_risk_not_bottleneck(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Reproduces the exact live-verified scenario (Dining Table x11,
    Chair x7, Bed Frame x3 against the 1250/8/100/576 wood/epoxy/
    nails/labor capacities) that motivated this feature: Labor lands
    at 572/576 = 99.31% - at_risk, not a bottleneck - while Epoxy
    (6.8/8 = 85%) is "high" and Wood/Nails stay "normal". Confirms the
    new status tiers sit alongside the untouched true-bottleneck rule
    (remaining_quantity <= 0) rather than replacing it.
    """

    products = {product.name: product for product in test_products}

    allocations = [
        _allocate(
            db,
            optimization_cycle.id,
            products["Test Dining Table"].id,
            Decimal("11"),
        ),
        _allocate(
            db,
            optimization_cycle.id,
            products["Test Chair"].id,
            Decimal("7"),
        ),
        _allocate(
            db,
            optimization_cycle.id,
            products["Test Bed Frame"].id,
            Decimal("3"),
        ),
    ]

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        assert response.status_code == 200

        data = response.json()

        by_name = {
            item["resource_name"]: item
            for item in data["resources"]
        }

        labor = by_name["Test Labor"]

        assert Decimal(labor["consumed_quantity"]) == Decimal("572")
        assert Decimal(labor["utilization_rate"]) == Decimal("99.31")
        assert labor["status"] == "at_risk"

        # At_risk is NOT a bottleneck - the untouched true-bottleneck
        # rule (remaining_quantity <= 0) still governs bottlenecks[].
        assert data["bottlenecks"] == []

        at_risk_names = {
            item["resource_name"]
            for item in data["at_risk_resources"]
        }
        assert at_risk_names == {"Test Labor"}

        assert by_name["Test Epoxy"]["status"] == "high"
        assert by_name["Test Wood"]["status"] == "normal"
        assert by_name["Test Nails"]["status"] == "normal"

        # Most constrained = highest utilization_rate across all
        # resources regardless of unit (Labor 99.31 > Epoxy 85 >
        # Wood 59.52 > Nails 5.55) - not a blended cross-unit sum.
        assert (
            data["most_constrained_resource"]["resource_name"]
            == "Test Labor"
        )

        # 3 material resources (Wood/Epoxy/Nails) - Labor is its own
        # "labor" category, not material. A count, never a summed
        # cross-unit quantity.
        assert data["material_resource_count"] == 3

    finally:
        for allocation in allocations:
            db.delete(allocation)

        db.commit()


def test_utilization_status_is_bottleneck_at_exactly_100_percent(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Epoxy consumption lands at exactly its 8-unit capacity (16 chairs
    x 0.5 epoxy each) - remaining_quantity == 0, the exact boundary of
    the pre-existing true-bottleneck rule. status must be "bottleneck"
    (not "at_risk"), and it must be excluded from at_risk_resources -
    a resource is never classified as both simultaneously.
    """

    allocation = _allocate(
        db,
        optimization_cycle.id,
        {p.name: p for p in test_products}["Test Chair"].id,
        Decimal("16"),
    )

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        data = response.json()

        epoxy = next(
            item
            for item in data["resources"]
            if item["resource_name"] == "Test Epoxy"
        )

        assert Decimal(epoxy["consumed_quantity"]) == Decimal("8")
        assert Decimal(epoxy["remaining_quantity"]) == Decimal("0")
        assert Decimal(epoxy["utilization_rate"]) == Decimal("100.00")
        assert epoxy["status"] == "bottleneck"

        at_risk_names = {
            item["resource_name"]
            for item in data["at_risk_resources"]
        }
        assert "Test Epoxy" not in at_risk_names

        bottleneck_names = {
            b["resource_name"] for b in data["bottlenecks"]
        }
        assert "Test Epoxy" in bottleneck_names

    finally:
        db.delete(allocation)
        db.commit()


def test_utilization_status_is_bottleneck_above_100_percent_with_shortage(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    17 chairs need 8.5 epoxy against an 8-unit capacity - over
    capacity, remaining_quantity < 0. status must be "bottleneck" and
    the existing shortage_quantity/is_binding fields stay correct
    (mirrors the pre-existing over-capacity assertions, extended with
    the new status field).
    """

    allocation = _allocate(
        db,
        optimization_cycle.id,
        {p.name: p for p in test_products}["Test Chair"].id,
        Decimal("17"),
    )

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        data = response.json()

        epoxy = next(
            item
            for item in data["resources"]
            if item["resource_name"] == "Test Epoxy"
        )

        assert Decimal(epoxy["remaining_quantity"]) == Decimal("-0.5")
        assert epoxy["status"] == "bottleneck"

        epoxy_bottleneck = next(
            b
            for b in data["bottlenecks"]
            if b["resource_name"] == "Test Epoxy"
        )
        assert epoxy_bottleneck["is_binding"] is False
        assert Decimal(
            epoxy_bottleneck["shortage_quantity"]
        ) == Decimal("0.5")

    finally:
        db.delete(allocation)
        db.commit()


def test_utilization_excludes_soft_deleted_resource_with_leftover_cycle_row(
    client,
    db,
    optimization_cycle,
):
    """
    Reproduces the "test" resource bug: a resource soft-deleted from
    Resources (is_active = False) whose CycleResource capacity row for
    the current cycle was never cleaned up must NOT still appear in
    the current utilization summary, and must not inflate its totals
    (material_resource_count, total_raw_materials_consumed, etc.).
    """

    inactive_resource = Resource(
        name="Regression Deleted Material",
        resource_type="material",
        unit="board ft",
        is_active=False,
    )
    db.add(inactive_resource)
    db.commit()
    db.refresh(inactive_resource)

    leftover_cycle_resource = CycleResource(
        production_cycle_id=optimization_cycle.id,
        resource_id=inactive_resource.id,
        available_quantity=Decimal("1.0000"),
        unit_price=Decimal("100.0000"),
    )
    db.add(leftover_cycle_resource)
    db.commit()

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        assert response.status_code == 200

        data = response.json()

        resource_names = {
            item["resource_name"] for item in data["resources"]
        }
        assert "Regression Deleted Material" not in resource_names

        # Unchanged from the no-allocations baseline - the leftover
        # inactive resource's available_quantity=1 must not be folded
        # into the active-resource totals.
        assert len(data["resources"]) == 4
        assert data["material_resource_count"] == 3

    finally:
        db.delete(leftover_cycle_resource)
        db.delete(inactive_resource)
        db.commit()


def test_utilization_ignores_optimization_preview_without_applied_allocation(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Resource Utilization must read applied ProductionAllocation rows
    only, never the optimizer's preview (OptimizationRun/
    OptimizationResult). Creates a preview-only optimization run/
    result for the cycle with NO corresponding ProductionAllocation,
    and confirms consumption is still reported as zero everywhere.
    """

    chair = {p.name: p for p in test_products}["Test Chair"]

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime.now(timezone.utc),
        status="OPTIMAL",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    result = OptimizationResult(
        optimization_run_id=run.id,
        product_id=chair.id,
        recommended_quantity=Decimal("50"),
        unit_profit=Decimal("100.0000"),
        total_profit=Decimal("5000.0000"),
    )
    db.add(result)
    db.commit()

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["bottlenecks"] == []
        assert data["at_risk_resources"] == []

        for item in data["resources"]:
            assert Decimal(item["consumed_quantity"]) == Decimal("0")
            assert item["status"] == "normal"

    finally:
        db.delete(run)
        db.commit()


def test_utilization_after_valid_apply_never_exceeds_capacity(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    A fresh, valid Apply (nothing changed in between) must produce a
    Resource Utilization report where every resource's required
    consumption stays within its available capacity - the capacity-
    integrity guards added to apply_optimization exist precisely to
    keep this true for anything freshly applied.
    """

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )

    assert response.status_code == 200
    data = response.json()

    for item in data["resources"]:
        assert Decimal(item["consumed_quantity"]) <= Decimal(
            item["available_quantity"]
        )
        assert Decimal(item["remaining_quantity"]) >= Decimal("0")


def test_consumption_override_replaces_allocation_derived_consumption(
    db, optimization_cycle, test_resources,
):
    """
    After a second application in a cycle, ProductionAllocation holds
    only the latest plan - so allocation-derived consumption
    understates what the cycle has actually spent. The override lets
    the caller supply the cumulative ledger figure instead.
    """

    from decimal import Decimal

    from app.services.resource_utilization import (
        calculate_resource_utilization,
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    result = calculate_resource_utilization(
        db,
        optimization_cycle.id,
        consumption_override={wood.id: Decimal("7")},
    )

    wood_row = next(
        row for row in result["resources"]
        if row["resource_id"] == wood.id
    )

    assert wood_row["consumed_quantity"] == Decimal("7")
    assert wood_row["remaining_quantity"] == (
        wood_row["available_quantity"] - Decimal("7")
    )


def test_omitting_the_override_preserves_allocation_derived_behaviour(
    db, optimization_cycle,
):
    from app.services.resource_utilization import (
        calculate_resource_utilization,
    )

    assert calculate_resource_utilization(
        db, optimization_cycle.id,
    ) == calculate_resource_utilization(
        db, optimization_cycle.id, consumption_override=None,
    )


# --- Weekly ("since quantity update") scoping for the Resource
# Utilization Report -------------------------------------------------
#
# A production "week" has no row of its own anywhere in this schema -
# editing a CycleResource's available_quantity in place (bumping its
# updated_at) IS how a new week starts in this system (see the
# Resource Utilization weekly-scoping investigation). These tests
# exercise get_cycle_consumed_by_resource_since_update directly
# against a real Generate+Apply flow, never the solver's predicted
# quantities by hand - only relative comparisons between the new
# scoped helper and the pre-existing all-time one.

def _generate_and_apply(client, cycle_id):
    optimize_response = client.post(
        f"/api/production-cycles/{cycle_id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200, optimize_response.text

    apply_response = client.post(
        f"/api/production-cycles/{cycle_id}/optimize/apply"
    )
    assert apply_response.status_code == 200, apply_response.text

    return optimize_response.json()


def test_since_update_matches_all_time_when_no_resource_was_ever_edited(
    client, db, optimization_cycle, test_products,
):
    """
    Regression guard: a cycle whose resources have never been edited
    since creation must see NO behavior change at all - the new
    scoped helper must return exactly what the existing all-time one
    does.
    """
    from app.services.production_application import (
        get_cycle_consumed_by_resource,
        get_cycle_consumed_by_resource_since_update,
    )

    _generate_and_apply(client, optimization_cycle.id)

    all_time = get_cycle_consumed_by_resource(db, optimization_cycle.id)
    since_update = get_cycle_consumed_by_resource_since_update(
        db, optimization_cycle.id,
    )

    assert since_update == all_time
    assert len(all_time) > 0


def test_since_update_still_accumulates_across_repeated_applies_without_an_edit(
    client, db, optimization_cycle, test_products,
):
    """
    Requirement 1: multiple successful Apply operations within the
    same production week (i.e. no resource quantity edit in between)
    must still accumulate - unchanged from today's behavior.
    """
    from app.services.production_application import (
        get_cycle_consumed_by_resource,
        get_cycle_consumed_by_resource_since_update,
    )

    _generate_and_apply(client, optimization_cycle.id)
    after_first = get_cycle_consumed_by_resource_since_update(
        db, optimization_cycle.id,
    )

    _generate_and_apply(client, optimization_cycle.id)
    after_second = get_cycle_consumed_by_resource_since_update(
        db, optimization_cycle.id,
    )

    # Every resource the first apply touched must show MORE consumed
    # after the second apply - genuine accumulation, not a reset.
    for resource_id, first_total in after_first.items():
        assert after_second[resource_id] > first_total

    # And still identical to the all-time helper, since nothing was
    # ever edited.
    assert after_second == get_cycle_consumed_by_resource(
        db, optimization_cycle.id,
    )


def test_since_update_excludes_consumption_from_before_a_quantity_edit(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    The core fix: editing a resource's quantity mid-cycle ("starting a
    new production week") must make the Resource Utilization Report
    count only consumption recorded SINCE that edit for THAT resource
    - while an untouched resource keeps accumulating exactly as
    before, and the full all-time history remains intact and
    unaffected in the database (requirement 3).
    """
    from app.services.production_application import (
        get_cycle_consumed_by_resource,
        get_cycle_consumed_by_resource_since_update,
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    _generate_and_apply(client, optimization_cycle.id)

    all_time_before_edit = get_cycle_consumed_by_resource(
        db, optimization_cycle.id,
    )
    assert wood.id in all_time_before_edit
    pre_edit_wood_consumption = all_time_before_edit[wood.id]

    # "A new production week": increase Wood's quantity in place -
    # the only mechanism this system has for starting one.
    patch_response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}"
        f"/resources/{wood.id}",
        json={"available_quantity": "2500.0000"},
    )
    assert patch_response.status_code == 200, patch_response.text

    _generate_and_apply(client, optimization_cycle.id)

    all_time_after = get_cycle_consumed_by_resource(
        db, optimization_cycle.id,
    )
    since_update_after = get_cycle_consumed_by_resource_since_update(
        db, optimization_cycle.id,
    )

    # Wood: the scoped total must be LESS than the all-time total by
    # exactly the pre-edit contribution - the second apply's own
    # consumption, and nothing from before the edit.
    assert (
        since_update_after[wood.id]
        == all_time_after[wood.id] - pre_edit_wood_consumption
    )
    assert since_update_after[wood.id] < all_time_after[wood.id]

    # Every OTHER resource (never edited) must be unaffected - scoped
    # and all-time totals still agree exactly.
    for resource_id, scoped_total in since_update_after.items():
        if resource_id == wood.id:
            continue

        assert scoped_total == all_time_after[resource_id]

    # Requirement 3: the pre-edit application record itself is still
    # fully present - get_cycle_consumed_by_resource (never scoped)
    # still reports the complete, untouched history.
    assert all_time_after[wood.id] >= pre_edit_wood_consumption


def test_latest_application_overconsumption_is_not_hidden_after_a_capacity_cut(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    Under the latest-application-only scoping, overconsumption must
    still never be silently hidden: a single apply followed by a
    resource capacity cut BELOW what that one application already
    consumed (no new apply since - still the latest application) must
    show negative remaining / >100% utilization, not a clamped
    "everything is fine" figure at the service layer (display-layer
    clamping is a separate, already-approved frontend concern, not
    tested here).
    """
    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    _generate_and_apply(client, optimization_cycle.id)

    from app.services.production_application import (
        get_latest_application_consumed_by_resource,
    )

    latest_consumed = get_latest_application_consumed_by_resource(
        db, optimization_cycle.id,
    )
    wood_consumed = latest_consumed[wood.id]
    assert wood_consumed > Decimal("0")

    # Cut Wood's capacity below what the (still-latest) application
    # already consumed - deliberately NO new apply after this.
    patch_response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}"
        f"/resources/{wood.id}",
        json={"available_quantity": str(wood_consumed - Decimal("1"))},
    )
    assert patch_response.status_code == 200, patch_response.text

    response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )
    assert response.status_code == 200
    data = response.json()

    wood_row = next(
        row for row in data["resources"]
        if row["resource_id"] == wood.id
    )

    assert Decimal(wood_row["consumed_quantity"]) == wood_consumed
    assert Decimal(wood_row["remaining_quantity"]) < Decimal("0")
    assert Decimal(wood_row["utilization_rate"]) > Decimal("100.00")
    assert wood_row["status"] == "bottleneck"


def test_since_update_also_resets_on_a_price_only_edit_known_limitation(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    KNOWN, REPORTED LIMITATION - not a silent side effect.

    CycleResource.updated_at is a single column shared by BOTH
    available_quantity and unit_price (confirmed in models.py and
    update_cycle_resource's plain setattr loop) - there is no separate
    "quantity last changed" timestamp without a schema change, which
    was explicitly out of scope for this fix. A price-only edit
    therefore ALSO resets get_cycle_consumed_by_resource_since_update's
    cutoff for that resource, even though no quantity actually
    changed. This test exists to make that limitation visible and
    verified, not to hide it - see get_cycle_consumed_by_resource_
    since_update's own docstring for the full explanation.
    """
    from app.services.production_application import (
        get_cycle_consumed_by_resource_since_update,
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    _generate_and_apply(client, optimization_cycle.id)

    before_price_edit = get_cycle_consumed_by_resource_since_update(
        db, optimization_cycle.id,
    )
    assert before_price_edit.get(wood.id, Decimal("0")) > Decimal("0")

    # Price-only edit - available_quantity is NOT sent at all.
    patch_response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}"
        f"/resources/{wood.id}",
        json={"unit_price": "99.0000"},
    )
    assert patch_response.status_code == 200, patch_response.text

    after_price_edit = get_cycle_consumed_by_resource_since_update(
        db, optimization_cycle.id,
    )

    # The documented limitation: a pure price edit still resets the
    # cutoff, so the prior apply's Wood consumption is now excluded
    # even though Wood's quantity itself never changed.
    assert wood.id not in after_price_edit


def test_since_update_excludes_both_earlier_weeks_after_a_second_edit(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    Gap identified in code review: editing the same resource TWICE in
    sequence must scope consumption to ONLY what's been applied since
    the SECOND (latest) edit - excluding both the pre-first-edit
    consumption AND the between-the-two-edits consumption, not just
    the oldest one. CycleResource.updated_at only ever stores the
    latest edit's timestamp (no history table), so this is the
    behavior the helper's single-cutoff-per-resource design implies -
    this test locks it in rather than leaving it verified by
    inspection only.
    """
    from app.services.production_application import (
        get_cycle_consumed_by_resource,
        get_cycle_consumed_by_resource_since_update,
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    # Week 1.
    _generate_and_apply(client, optimization_cycle.id)

    # Week 2 starts: first edit.
    first_edit = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}"
        f"/resources/{wood.id}",
        json={"available_quantity": "2500.0000"},
    )
    assert first_edit.status_code == 200, first_edit.text

    _generate_and_apply(client, optimization_cycle.id)

    all_time_after_week_2 = get_cycle_consumed_by_resource(
        db, optimization_cycle.id,
    )

    # Week 3 starts: second edit, superseding the first.
    second_edit = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}"
        f"/resources/{wood.id}",
        json={"available_quantity": "3000.0000"},
    )
    assert second_edit.status_code == 200, second_edit.text

    _generate_and_apply(client, optimization_cycle.id)

    all_time_after_week_3 = get_cycle_consumed_by_resource(
        db, optimization_cycle.id,
    )
    since_update_after_week_3 = (
        get_cycle_consumed_by_resource_since_update(
            db, optimization_cycle.id,
        )
    )

    # Scoped total for Wood must equal EXACTLY week 3's own
    # contribution - all_time(week 1+2+3) minus all_time(week 1+2)
    # leaves only week 3's increment, with both earlier weeks
    # excluded, not just the oldest one.
    week_3_only_contribution = (
        all_time_after_week_3[wood.id] - all_time_after_week_2[wood.id]
    )

    assert (
        since_update_after_week_3[wood.id] == week_3_only_contribution
    )
    assert (
        since_update_after_week_3[wood.id]
        < all_time_after_week_3[wood.id]
    )

    # Every other, never-edited resource keeps accumulating across
    # all three weeks exactly as before.
    for resource_id, scoped_total in since_update_after_week_3.items():
        if resource_id == wood.id:
            continue

        assert scoped_total == all_time_after_week_3[resource_id]


def test_since_update_includes_an_application_applied_exactly_at_the_cutoff(
    db, test_resources, test_products,
):
    """
    Gap identified in code review: the exclusion condition is
    `applied_at < cutoff`, meaning an application whose applied_at is
    EXACTLY EQUAL to the resource's updated_at must be INCLUDED, never
    excluded. Real HTTP-driven timestamps never produce an exact tie
    (microsecond-precision wall-clock values essentially never
    collide), so this constructs the tie directly and deterministically
    instead of relying on timing.
    """
    from app.database.models import (
        CycleResource,
        OptimizationRun,
        ProductionApplication,
        ProductionApplicationResourceItem,
        ProductionCycle,
    )
    from app.services.production_application import (
        get_cycle_consumed_by_resource_since_update,
    )

    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 6, 1),
        start_date=datetime(2026, 6, 1),
        end_date=datetime(2026, 6, 1),
        status="PLANNED",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    exact_instant = datetime(2026, 6, 1, 12, 0, 0)

    cycle_resource = CycleResource(
        production_cycle_id=cycle.id,
        resource_id=wood.id,
        available_quantity=Decimal("1000.0000"),
        unit_price=Decimal("84.0000"),
    )
    db.add(cycle_resource)
    db.commit()
    db.refresh(cycle_resource)

    # Force updated_at to the exact tie instant - bypasses the
    # onupdate default, which only fills in a value for a column NOT
    # explicitly assigned in this flush.
    cycle_resource.updated_at = exact_instant
    db.add(cycle_resource)
    db.commit()

    run = OptimizationRun(
        production_cycle_id=cycle.id,
        started_at=exact_instant,
        status="OPTIMAL",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    application = ProductionApplication(
        application_number="PA-TIE-TEST",
        production_cycle_id=cycle.id,
        optimization_run_id=run.id,
        applied_at=exact_instant,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    resource_item = ProductionApplicationResourceItem(
        production_application_id=application.id,
        resource_id=wood.id,
        resource_name=wood.name,
        unit=wood.unit,
        consumed_quantity=Decimal("123.4500"),
    )
    db.add(resource_item)
    db.commit()

    # Sanity check the tie was actually constructed as intended before
    # asserting anything about the function under test.
    db.refresh(cycle_resource)
    db.refresh(application)
    assert cycle_resource.updated_at == exact_instant
    assert application.applied_at == exact_instant

    try:
        since_update = get_cycle_consumed_by_resource_since_update(
            db, cycle.id,
        )

        assert since_update.get(wood.id) == Decimal("123.4500")

    finally:
        db.delete(resource_item)
        db.delete(application)
        db.delete(run)
        db.delete(cycle_resource)
        db.delete(cycle)
        db.commit()


def test_latest_cycle_route_uses_only_the_latest_application(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    Exercises the bare /api/resource-utilization ("latest cycle")
    route the same way the explicit-cycle route is exercised
    elsewhere in this file, confirming it too reports ONLY the latest
    application's own consumption - not the all-time cumulative total
    across both applies made here.
    """
    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    _generate_and_apply(client, optimization_cycle.id)
    _generate_and_apply(client, optimization_cycle.id)

    response = client.get("/api/resource-utilization")
    assert response.status_code == 200

    data = response.json()
    assert data["cycle_id"] == optimization_cycle.id

    wood_row = next(
        row for row in data["resources"]
        if row["resource_id"] == wood.id
    )

    # If the latest-cycle route were still summing every application,
    # consumed_quantity here would include BOTH applies' worth of
    # Wood - this asserts it reflects only the second (latest) one.
    from app.services.production_application import (
        get_cycle_consumed_by_resource,
        get_latest_application_consumed_by_resource,
    )

    all_time = get_cycle_consumed_by_resource(db, optimization_cycle.id)
    latest_only = get_latest_application_consumed_by_resource(
        db, optimization_cycle.id,
    )

    assert latest_only[wood.id] < all_time[wood.id]
    assert Decimal(wood_row["consumed_quantity"]) == latest_only[wood.id]


# --- Empty-scoped-consumption fallback fix ---------------------------
#
# Bug: consumption_override=consumed or None in both Resource
# Utilization GET handlers treated an EMPTY dict from
# get_cycle_consumed_by_resource_since_update as equivalent to "no
# override at all", falling through to calculate_resource_utilization's
# allocation-derived branch - which reads the CURRENT ProductionAllocation
# row (the last applied plan) and silently resurrects its stale,
# pre-edit consumption. This is reachable any time editing a cycle's
# resource(s) ("starting a new week") makes every one of that cycle's
# qualifying applications fall before their own resource's cutoff -
# trivially true for a single-resource cycle, and for the realistic
# "edit every resource together" workflow on a multi-resource one.
#
# Fix: pass `consumed` straight through, never collapsed through
# `or None`. calculate_resource_utilization already defaults any
# resource missing from the dict to Decimal("0") on its own, so an
# empty dict already means "zero consumption for everything" with no
# fallback required - correct both right after an edit (nothing
# applied since) and for a cycle with no applications at all.
#
# Scope: this fix lives entirely in resource_utilization.py's two GET
# handlers. Resource Management (CRUD, quantity/price update
# behavior, validation, models/schema, update_at semantics) is
# untouched - these tests only assert on what the Resource Utilization
# Report returns, never on Resource Management's own behavior.

def test_edit_without_new_apply_keeps_showing_the_latest_applied_consumption(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    Editing a cycle's resources does not create a new
    ProductionApplication, so it must NOT change which application is
    "latest": apply once, edit EVERY resource on the cycle, then check
    the report WITHOUT applying again - the report must keep showing
    that one application's own consumption unchanged (never reset to
    zero just because capacity was edited), while remaining_quantity/
    utilization_rate/status recompute against the NEW availability.
    """
    _generate_and_apply(client, optimization_cycle.id)

    before_edit = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )
    assert before_edit.status_code == 200

    consumed_before = {
        row["resource_id"]: Decimal(row["consumed_quantity"])
        for row in before_edit.json()["resources"]
    }
    assert any(
        quantity > Decimal("0")
        for quantity in consumed_before.values()
    )

    for resource in test_resources:
        patch_response = client.patch(
            f"/api/production-cycles/{optimization_cycle.id}"
            f"/resources/{resource.id}",
            json={"available_quantity": "2500.0000"},
        )
        assert patch_response.status_code == 200, patch_response.text

    # Deliberately NO new Generate/Apply here.
    response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )
    assert response.status_code == 200
    data = response.json()

    for row in data["resources"]:
        resource_id = row["resource_id"]

        assert Decimal(row["consumed_quantity"]) == (
            consumed_before[resource_id]
        )
        assert Decimal(row["remaining_quantity"]) == (
            Decimal("2500.0000") - consumed_before[resource_id]
        )


def test_edit_without_new_apply_keeps_latest_consumption_on_the_latest_cycle_route_too(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    Same scenario, exercised through the OTHER GET handler
    (/api/resource-utilization, latest-cycle) - both call sites share
    the identical latest-application-only scoping.
    """
    _generate_and_apply(client, optimization_cycle.id)

    before_edit = client.get("/api/resource-utilization")
    assert before_edit.status_code == 200

    consumed_before = {
        row["resource_id"]: Decimal(row["consumed_quantity"])
        for row in before_edit.json()["resources"]
    }
    assert any(
        quantity > Decimal("0")
        for quantity in consumed_before.values()
    )

    for resource in test_resources:
        patch_response = client.patch(
            f"/api/production-cycles/{optimization_cycle.id}"
            f"/resources/{resource.id}",
            json={"available_quantity": "2500.0000"},
        )
        assert patch_response.status_code == 200, patch_response.text

    response = client.get("/api/resource-utilization")
    assert response.status_code == 200
    data = response.json()
    assert data["cycle_id"] == optimization_cycle.id

    for row in data["resources"]:
        assert Decimal(row["consumed_quantity"]) == (
            consumed_before[row["resource_id"]]
        )


def test_single_resource_cycle_edit_without_new_apply_keeps_latest_consumption(
    client, db,
):
    """
    The narrowest case: a cycle with only ONE resource. Editing it
    with no new apply since must NOT reset the report to zero - the
    latest (and only) application is still the latest application.
    Built from scratch (not optimization_cycle's 4 shared resources)
    to isolate this single-resource edge case cleanly.
    """
    from app.database.models import (
        Product,
        ProductionCycle,
        ProductResourceRequirement,
        Resource,
        CycleResource,
    )
    from app.services.auth import hash_password
    from app.database.models import User

    db.query(User).filter(
        User.username == "single_resource_regression_user"
    ).delete()
    db.commit()

    user = User(
        username="single_resource_regression_user",
        email="single_resource_regression_user@example.com",
        password_hash=hash_password("RegressionPassword9!"),
        is_active=True,
    )
    db.add(user)
    db.commit()

    wood = Resource(
        name="Regression Single Wood",
        resource_type="material",
        unit="bf",
        is_active=True,
    )
    db.add(wood)
    db.commit()
    db.refresh(wood)

    table = Product(
        name="Regression Single Table",
        selling_price=Decimal("1000.00"),
        labor_cost=Decimal("0.00"),
        minimum_demand=Decimal("1"),
        is_active=True,
    )
    db.add(table)
    db.commit()
    db.refresh(table)

    requirement = ProductResourceRequirement(
        product_id=table.id,
        resource_id=wood.id,
        quantity_required=Decimal("10.0000"),
    )
    db.add(requirement)
    db.commit()

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 2, 1),
        start_date=datetime(2026, 2, 1),
        end_date=datetime(2026, 2, 8),
        status="OPEN",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    cycle_resource = CycleResource(
        production_cycle_id=cycle.id,
        resource_id=wood.id,
        available_quantity=Decimal("100.0000"),
        unit_price=Decimal("1.00"),
    )
    db.add(cycle_resource)
    db.commit()

    try:
        login = client.post(
            "/api/auth/login",
            json={
                "username": "single_resource_regression_user",
                "password": "RegressionPassword9!",
            },
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        optimize_response = client.post(
            f"/api/production-cycles/{cycle.id}/optimize",
            json={"objective": "MAX_PROFIT"},
            headers=headers,
        )
        assert optimize_response.status_code == 200, optimize_response.text

        apply_response = client.post(
            f"/api/production-cycles/{cycle.id}/optimize/apply",
            headers=headers,
        )
        assert apply_response.status_code == 200, apply_response.text

        before_edit = client.get(
            f"/api/resource-utilization/{cycle.id}", headers=headers,
        )
        wood_before = before_edit.json()["resources"][0]
        wood_consumed = Decimal(wood_before["consumed_quantity"])
        assert wood_consumed > Decimal("0")

        patch_response = client.patch(
            f"/api/production-cycles/{cycle.id}/resources/{wood.id}",
            json={"available_quantity": "500.0000"},
            headers=headers,
        )
        assert patch_response.status_code == 200, patch_response.text

        response = client.get(
            f"/api/resource-utilization/{cycle.id}", headers=headers,
        )
        assert response.status_code == 200
        data = response.json()

        wood_row = data["resources"][0]
        assert Decimal(wood_row["consumed_quantity"]) == wood_consumed
        assert Decimal(wood_row["remaining_quantity"]) == (
            Decimal("500.0000") - wood_consumed
        )

    finally:
        from app.database.models import (
            ProductionAllocation,
            ProductionApplication,
            ProductionApplicationItem,
            ProductionApplicationResourceItem,
            OptimizationResult,
            OptimizationRun,
        )

        application_ids = [
            row[0] for row in db.query(ProductionApplication.id).filter(
                ProductionApplication.production_cycle_id == cycle.id
            ).all()
        ]

        if application_ids:
            db.query(ProductionApplicationResourceItem).filter(
                ProductionApplicationResourceItem
                .production_application_id.in_(application_ids)
            ).delete(synchronize_session=False)
            db.query(ProductionApplicationItem).filter(
                ProductionApplicationItem.production_application_id.in_(
                    application_ids
                )
            ).delete(synchronize_session=False)
            db.query(ProductionApplication).filter(
                ProductionApplication.id.in_(application_ids)
            ).delete(synchronize_session=False)

        db.query(ProductionAllocation).filter(
            ProductionAllocation.production_cycle_id == cycle.id
        ).delete(synchronize_session=False)

        run_ids = [
            row[0] for row in db.query(OptimizationRun.id).filter(
                OptimizationRun.production_cycle_id == cycle.id
            ).all()
        ]
        if run_ids:
            db.query(OptimizationResult).filter(
                OptimizationResult.optimization_run_id.in_(run_ids)
            ).delete(synchronize_session=False)
            db.query(OptimizationRun).filter(
                OptimizationRun.id.in_(run_ids)
            ).delete(synchronize_session=False)

        db.query(CycleResource).filter(
            CycleResource.production_cycle_id == cycle.id
        ).delete(synchronize_session=False)
        db.delete(cycle)
        db.delete(requirement)
        db.delete(table)
        db.delete(wood)
        db.query(User).filter(
            User.username == "single_resource_regression_user"
        ).delete()
        db.commit()


# --- Latest-successful-application-only scoping -----------------------
#
# Business requirement: the Resource Utilization Report must show the
# LATEST successfully applied Production Allocation only - Generate #2
# -> Apply must REPLACE what #1 showed, never add to it. See
# get_latest_application_consumed_by_resource (production_application.py)
# and resource_utilization.py's two GET handlers.

WOOD_PER_UNIT_BY_PRODUCT_NAME = {
    "Test Dining Table": Decimal("45"),
    "Test Chair": Decimal("12"),
    "Test Bed Frame": Decimal("55"),
}


def _expected_wood_consumed(allocations, products_by_id):
    total = Decimal("0")

    for allocation in allocations:
        product = products_by_id[allocation["product_id"]]
        per_unit = WOOD_PER_UNIT_BY_PRODUCT_NAME.get(
            product.name, Decimal("0"),
        )
        total += per_unit * Decimal(str(allocation["quantity"]))

    return total


def test_first_application_displays_its_own_consumption(
    client, db, optimization_cycle, test_products, test_resources,
):
    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )
    products_by_id = {product.id: product for product in test_products}

    result = _generate_and_apply(client, optimization_cycle.id)
    expected_wood = _expected_wood_consumed(
        result["allocations"], products_by_id,
    )
    assert expected_wood > Decimal("0")

    response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )
    assert response.status_code == 200

    wood_row = next(
        row for row in response.json()["resources"]
        if row["resource_id"] == wood.id
    )

    assert Decimal(wood_row["consumed_quantity"]) == expected_wood


def test_three_sequential_applications_each_replace_the_previous_report(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    Generate Allocation #1 -> Apply -> report shows #1's consumption.
    Generate Allocation #2 (genuinely different, forced by a Wood
    capacity edit between rounds) -> Apply -> report REPLACES it with
    #2's. Generate Allocation #3 -> Apply -> report REPLACES it with
    #3's. At no point does the report equal a running sum of earlier
    rounds.
    """
    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )
    products_by_id = {product.id: product for product in test_products}

    wood_capacities = ["1250.0000", "900.0000", "1500.0000"]
    expected_per_round = []
    reported_per_round = []

    for capacity in wood_capacities:
        patch_response = client.patch(
            f"/api/production-cycles/{optimization_cycle.id}"
            f"/resources/{wood.id}",
            json={"available_quantity": capacity},
        )
        assert patch_response.status_code == 200, patch_response.text

        result = _generate_and_apply(client, optimization_cycle.id)
        expected = _expected_wood_consumed(
            result["allocations"], products_by_id,
        )
        expected_per_round.append(expected)

        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )
        assert response.status_code == 200

        wood_row = next(
            row for row in response.json()["resources"]
            if row["resource_id"] == wood.id
        )
        reported_per_round.append(Decimal(wood_row["consumed_quantity"]))

    # Each round's report matches exactly that round's own allocation -
    # never a running sum of this round plus any earlier one.
    assert reported_per_round == expected_per_round

    running_sum = Decimal("0")
    for expected, reported in zip(expected_per_round, reported_per_round):
        running_sum += expected
        # Once more than one round has happened, the buggy
        # accumulated total would differ from the correct per-round
        # figure (unless a round legitimately consumed zero).
        if expected > Decimal("0") and running_sum != expected:
            assert reported != running_sum


def test_previous_application_records_remain_in_the_database(
    client, db, optimization_cycle, test_products,
):
    """
    Scoping the REPORT to the latest application must never delete or
    modify any earlier ProductionApplication row - all of them stay
    fully queryable, each with its own correct resource/product items.
    """
    from app.database.models import ProductionApplication

    application_ids = []

    for _ in range(3):
        _generate_and_apply(client, optimization_cycle.id)

        latest = (
            db.query(ProductionApplication)
            .filter(
                ProductionApplication.production_cycle_id
                == optimization_cycle.id
            )
            .order_by(
                ProductionApplication.applied_at.desc(),
                ProductionApplication.id.desc(),
            )
            .first()
        )
        application_ids.append(latest.id)

    assert len(set(application_ids)) == 3

    db.expire_all()

    for application_id in application_ids:
        application = db.get(ProductionApplication, application_id)
        assert application is not None
        assert len(application.resource_items) > 0


def test_different_cycles_do_not_affect_each_others_report(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    A second, independent cycle's Apply must never change what the
    first cycle's Resource Utilization Report shows, and vice versa -
    "latest application" is resolved PER CYCLE.
    """
    from app.database.models import CycleResource, ProductionCycle

    other_cycle = ProductionCycle(
        cycle_date=datetime(2026, 9, 1),
        start_date=datetime(2026, 9, 1),
        end_date=datetime(2026, 9, 8),
        status="OPEN",
    )
    db.add(other_cycle)
    db.commit()
    db.refresh(other_cycle)

    for resource in test_resources:
        db.add(
            CycleResource(
                production_cycle_id=other_cycle.id,
                resource_id=resource.id,
                available_quantity=Decimal("1250.0000"),
                unit_price=Decimal("10.00"),
            )
        )
    db.commit()

    try:
        _generate_and_apply(client, optimization_cycle.id)

        first_cycle_report = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        ).json()

        _generate_and_apply(client, other_cycle.id)

        other_cycle_report = client.get(
            f"/api/resource-utilization/{other_cycle.id}"
        ).json()

        # Re-fetch the first cycle's report - applying to the OTHER
        # cycle must not have changed it at all.
        first_cycle_report_after = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        ).json()

        assert (
            first_cycle_report["resources"]
            == first_cycle_report_after["resources"]
        )
        assert other_cycle_report["cycle_id"] == other_cycle.id
        assert first_cycle_report["cycle_id"] == optimization_cycle.id

    finally:
        from app.database.models import (
            OptimizationResult,
            OptimizationRun,
            ProductionAllocation,
            ProductionApplication,
            ProductionApplicationItem,
            ProductionApplicationResourceItem,
        )

        application_ids = [
            row[0] for row in db.query(ProductionApplication.id).filter(
                ProductionApplication.production_cycle_id
                == other_cycle.id
            ).all()
        ]

        if application_ids:
            db.query(ProductionApplicationResourceItem).filter(
                ProductionApplicationResourceItem
                .production_application_id.in_(application_ids)
            ).delete(synchronize_session=False)
            db.query(ProductionApplicationItem).filter(
                ProductionApplicationItem.production_application_id.in_(
                    application_ids
                )
            ).delete(synchronize_session=False)
            db.query(ProductionApplication).filter(
                ProductionApplication.id.in_(application_ids)
            ).delete(synchronize_session=False)

        db.query(ProductionAllocation).filter(
            ProductionAllocation.production_cycle_id == other_cycle.id
        ).delete(synchronize_session=False)

        run_ids = [
            row[0] for row in db.query(OptimizationRun.id).filter(
                OptimizationRun.production_cycle_id == other_cycle.id
            ).all()
        ]
        if run_ids:
            db.query(OptimizationResult).filter(
                OptimizationResult.optimization_run_id.in_(run_ids)
            ).delete(synchronize_session=False)
            db.query(OptimizationRun).filter(
                OptimizationRun.id.in_(run_ids)
            ).delete(synchronize_session=False)

        db.query(CycleResource).filter(
            CycleResource.production_cycle_id == other_cycle.id
        ).delete(synchronize_session=False)
        db.delete(other_cycle)
        db.commit()


def test_failed_apply_does_not_become_the_latest_application(
    client, db, optimization_cycle, test_products,
):
    """
    A failed/rejected Apply attempt (here: re-applying the same
    already-applied optimization run, rejected by
    has_application_for_run's guard) must never change which
    application the report considers "latest" - apply_optimization
    raises and rolls back before writing anything, so there is no new
    row for this attempt to have become latest with.
    """
    _generate_and_apply(client, optimization_cycle.id)

    before = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    ).json()

    # Re-apply with no new Generate in between - rejected by the
    # duplicate-application guard, nothing written.
    duplicate_apply = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert duplicate_apply.status_code == 400

    after = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    ).json()

    assert after["resources"] == before["resources"]


def test_kpi_table_and_chart_data_come_from_the_same_scoped_response(
    client, db, optimization_cycle, test_products, test_resources,
):
    """
    KPI cards, the utilization table, the chart, and bottleneck
    analysis are all derived client-side (utilizationAdapter.ts) from
    this ONE response - so backend-level internal consistency here is
    exactly what guarantees the frontend never shows mismatched
    figures: totals, per-resource rows, and bottlenecks must all
    agree with each other within a single response.
    """
    _generate_and_apply(client, optimization_cycle.id)

    response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )
    assert response.status_code == 200
    data = response.json()

    resources_by_id = {
        row["resource_id"]: row for row in data["resources"]
    }

    # Bottleneck analysis must reference the SAME consumed/remaining
    # figures as the table rows, not an independently recomputed set.
    for bottleneck in data["bottlenecks"]:
        row = resources_by_id[bottleneck["resource_id"]]
        assert (
            Decimal(bottleneck["remaining_quantity"])
            == Decimal(row["remaining_quantity"])
        )

    # KPI totals (total_raw_materials_consumed, labor/machine hours)
    # must reconcile with a fresh sum over the same per-resource rows.
    materials_total = sum(
        Decimal(row["consumed_quantity"])
        for row in data["resources"]
        if row["resource_type"].strip().lower() not in (
            "labor", "machine",
        )
    )
    assert materials_total == Decimal(
        data["total_raw_materials_consumed"]
    )

    labor_total = sum(
        Decimal(row["consumed_quantity"])
        for row in data["resources"]
        if row["resource_type"].strip().lower() == "labor"
    )
    assert labor_total == Decimal(data["total_labor_hours_used"])

    # most_constrained_resource (feeds the chart's highlighted bar)
    # must be one of the same resources, with a matching rate.
    most_constrained = data["most_constrained_resource"]
    assert most_constrained is not None
    matching_row = resources_by_id[most_constrained["resource_id"]]
    assert (
        Decimal(most_constrained["utilization_rate"])
        == Decimal(matching_row["utilization_rate"])
    )
