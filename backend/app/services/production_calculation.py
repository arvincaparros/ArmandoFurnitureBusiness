from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CycleResource,
    ProductResourceRequirement,
    ProductionAllocation,
    Resource,
)


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