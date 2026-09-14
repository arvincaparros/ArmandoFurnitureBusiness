from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CycleResource,
    ProductResourceRequirement,
    ProductionAllocation,
    Resource,
)


# Shared by resource_utilization.py and optimization.py so both
# services express the same true-bottleneck condition and the newer
# utilization-status tiers (resource_utilization.py) come from one
# named place instead of scattered magic numbers. The true bottleneck
# rule stays remaining_quantity <= 0 (BOTTLENECK_REMAINING_THRESHOLD)
# in both services - unchanged - the three *_UTILIZATION_THRESHOLD
# constants only add a status classification on top of the already-
# computed utilization_rate, they don't replace that rule.
BOTTLENECK_REMAINING_THRESHOLD = Decimal("0")
HIGH_UTILIZATION_THRESHOLD = Decimal("80")
AT_RISK_UTILIZATION_THRESHOLD = Decimal("90")
BOTTLENECK_UTILIZATION_THRESHOLD = Decimal("100")


def calculate_resource_consumption(
    db: Session,
    cycle_id: int,
) -> list[dict]:
    """
    Calculate total resource consumption for all allocations
    in a production cycle.
    """

    statement = (
        select(
            ProductionAllocation.product_id,
            Resource.id.label("resource_id"),
            Resource.name.label("resource_name"),
            Resource.unit.label("unit"),
            ProductResourceRequirement.quantity_required,
            ProductionAllocation.quantity.label(
                "allocated_quantity"
            ),
        )
        .join(
            ProductResourceRequirement,
            ProductResourceRequirement.product_id
            == ProductionAllocation.product_id,
        )
        .join(
            Resource,
            Resource.id
            == ProductResourceRequirement.resource_id,
        )
        .where(
            ProductionAllocation.production_cycle_id == cycle_id,
        )
    )

    rows = db.execute(statement).all()

    consumption: dict[int, dict] = {}

    for row in rows:
        resource_id = row.resource_id

        required_quantity = (
            row.quantity_required
            * row.allocated_quantity
        )

        if resource_id not in consumption:
            consumption[resource_id] = {
                "resource_id": resource_id,
                "resource_name": row.resource_name,
                "unit": row.unit,
                "required_quantity": Decimal("0"),
            }

        consumption[resource_id]["required_quantity"] += (
            required_quantity
        )

    return list(consumption.values())


def check_allocation_feasibility(
    db: Session,
    cycle_id: int,
) -> dict:
    """
    Compare calculated resource consumption against
    the resources available in a production cycle.
    """

    consumption = calculate_resource_consumption(
        db,
        cycle_id,
    )

    resources = []

    for item in consumption:
        cycle_resource_statement = select(
            CycleResource
        ).where(
            CycleResource.production_cycle_id == cycle_id,
            CycleResource.resource_id == item["resource_id"],
        )

        cycle_resource = db.scalars(
            cycle_resource_statement
        ).first()

        if cycle_resource is None:
            available_quantity = Decimal("0")
        else:
            available_quantity = (
                cycle_resource.available_quantity
            )

        required_quantity = item["required_quantity"]

        remaining_quantity = (
            available_quantity - required_quantity
        )

        is_feasible = (
            required_quantity <= available_quantity
        )

        resources.append(
            {
                "resource_id": item["resource_id"],
                "resource_name": item["resource_name"],
                "unit": item["unit"],
                "required_quantity": required_quantity,
                "available_quantity": available_quantity,
                "remaining_quantity": remaining_quantity,
                "is_feasible": is_feasible,
            }
        )

    is_feasible = all(
        resource["is_feasible"]
        for resource in resources
    )

    bottlenecks = [
        {
            "resource_id": resource["resource_id"],
            "resource_name": resource["resource_name"],
            "unit": resource["unit"],
            "shortage_quantity": abs(
                resource["remaining_quantity"]
            ),
        }
        for resource in resources
        if not resource["is_feasible"]
    ]

    return {
        "cycle_id": cycle_id,
        "is_feasible": is_feasible,
        "resources": resources,
        "bottlenecks": bottlenecks,
    }


# --- Capacity-integrity write-boundary guards -------------------------------
#
# The three functions below are deliberately NOT built on top of
# calculate_resource_consumption/check_allocation_feasibility above:
# those read consumption straight from already-COMMITTED
# ProductionAllocation rows via a live SQL join, which fits their
# purpose (report on what's actually applied right now) but not this
# one - validating a PROPOSED set of quantities (a manual allocation
# edit, an about-to-be-applied optimization result, or a proposed
# requirement change) BEFORE it's committed. Forcing reuse here would
# mean changing calculate_resource_consumption's query shape or
# check_allocation_feasibility's return shape for a purpose neither
# was designed for - so this shares the same aggregation approach
# (join through ProductResourceRequirement/Resource, sum per
# resource_id) without sharing the same function body, and
# check_allocation_feasibility itself is untouched.


def calculate_resource_requirements_for_quantities(
    db: Session,
    quantities_by_product_id: dict[int, Decimal],
    requirement_override: tuple[int, int, Decimal] | None = None,
) -> list[dict]:
    """
    Total resource consumption for an explicit, proposed set of
    product quantities - NOT necessarily what's currently persisted in
    ProductionAllocation.

    requirement_override optionally substitutes one specific
    (product_id, resource_id) requirement's quantity_required with a
    proposed new value, for validating a requirement edit before it's
    committed - every other requirement is read at its current,
    already-persisted value.
    """

    product_ids = [
        product_id
        for product_id, quantity in quantities_by_product_id.items()
        if quantity > 0
    ]

    if not product_ids:
        return []

    requirement_rows = db.execute(
        select(ProductResourceRequirement, Resource)
        .join(
            Resource,
            Resource.id == ProductResourceRequirement.resource_id,
        )
        .where(
            ProductResourceRequirement.product_id.in_(product_ids)
        )
    ).all()

    consumption: dict[int, dict] = {}

    for requirement, resource in requirement_rows:
        quantity = quantities_by_product_id.get(
            requirement.product_id,
            Decimal("0"),
        )

        if quantity <= 0:
            continue

        quantity_required = requirement.quantity_required

        if (
            requirement_override is not None
            and requirement.product_id == requirement_override[0]
            and requirement.resource_id == requirement_override[1]
        ):
            quantity_required = requirement_override[2]

        if requirement.resource_id not in consumption:
            consumption[requirement.resource_id] = {
                "resource_id": requirement.resource_id,
                "resource_name": resource.name,
                "unit": resource.unit,
                "resource_is_active": resource.is_active,
                "required_quantity": Decimal("0"),
            }

        consumption[requirement.resource_id]["required_quantity"] += (
            quantity_required * quantity
        )

    return list(consumption.values())


def find_resource_capacity_shortages(
    db: Session,
    cycle_id: int,
    quantities_by_product_id: dict[int, Decimal],
    requirement_override: tuple[int, int, Decimal] | None = None,
) -> list[dict]:
    """
    Checks a PROPOSED set of product quantities against this cycle's
    CURRENT CycleResource capacity - an inactive resource is treated
    as zero available capacity here too (matching
    optimization.py::add_resource_constraints' convention), never its
    stale available_quantity, and never fabricated as unlimited when
    there's no CycleResource row for it at all this cycle. Returns one
    shortage dict per over-capacity resource - an empty list means the
    proposal fits entirely within current capacity.
    """

    consumption = calculate_resource_requirements_for_quantities(
        db,
        quantities_by_product_id,
        requirement_override,
    )

    cycle_resources_by_id = {
        cycle_resource.resource_id: cycle_resource
        for cycle_resource in db.scalars(
            select(CycleResource).where(
                CycleResource.production_cycle_id == cycle_id
            )
        ).all()
    }

    shortages = []

    for item in consumption:
        cycle_resource = cycle_resources_by_id.get(item["resource_id"])

        if cycle_resource is None:
            available_quantity = Decimal("0")
        elif not item["resource_is_active"]:
            available_quantity = Decimal("0")
        else:
            available_quantity = cycle_resource.available_quantity

        required_quantity = item["required_quantity"]

        if required_quantity > available_quantity:
            shortages.append(
                {
                    "resource_id": item["resource_id"],
                    "resource_name": item["resource_name"],
                    "unit": item["unit"],
                    "required_quantity": required_quantity,
                    "available_quantity": available_quantity,
                    "shortage_quantity": (
                        required_quantity - available_quantity
                    ),
                }
            )

    return shortages


def format_capacity_shortage_message(
    shortages: list[dict],
    prefix: str,
) -> str:
    """
    Shared error-message formatting for every capacity-integrity guard
    (manual allocation create/update, apply revalidation, capacity/
    requirement edits) - always names the resource(s), the required
    and available amounts, and the shortage.
    """

    details = "; ".join(
        f"{shortage['resource_name']} requires "
        f"{shortage['required_quantity']} {shortage['unit']}, only "
        f"{shortage['available_quantity']} {shortage['unit']} "
        f"available (short by {shortage['shortage_quantity']} "
        f"{shortage['unit']})"
        for shortage in shortages
    )

    return f"{prefix}: {details}."