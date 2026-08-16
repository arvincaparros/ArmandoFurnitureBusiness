from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ProductionCycle, Resource
from app.services.cycle_resource import get_cycle_resources
from app.services.production_calculation import (
    AT_RISK_UTILIZATION_THRESHOLD,
    BOTTLENECK_REMAINING_THRESHOLD,
    BOTTLENECK_UTILIZATION_THRESHOLD,
    HIGH_UTILIZATION_THRESHOLD,
    calculate_resource_consumption,
)


def get_latest_production_cycle_id(db: Session) -> int | None:
    statement = (
        select(ProductionCycle.id)
        .order_by(
            ProductionCycle.created_at.desc(),
            ProductionCycle.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)


def _classify_resource_type(resource_type: str) -> str:
    normalized = resource_type.strip().lower()

    if normalized == "labor":
        return "labor"

    if normalized == "machine":
        return "machine"

    return "material"


def classify_utilization_status(utilization_rate: Decimal) -> str:
    """
    Four-tier capacity status derived from the already-computed
    utilization_rate (consumed/available * 100) - a classification of
    an existing number, not a new calculation. utilization_rate >= 100
    is exactly equivalent to remaining_quantity <= 0 (the pre-existing
    true bottleneck rule, unchanged) whenever available_quantity > 0.
    """

    if utilization_rate >= BOTTLENECK_UTILIZATION_THRESHOLD:
        return "bottleneck"

    if utilization_rate >= AT_RISK_UTILIZATION_THRESHOLD:
        return "at_risk"

    if utilization_rate >= HIGH_UTILIZATION_THRESHOLD:
        return "high"

    return "normal"


def calculate_resource_utilization(
    db: Session,
    cycle_id: int,
) -> dict:
    """
    Aggregate resource utilization for a production cycle from
    existing cycle resource capacity and existing allocation-based
    consumption calculations.
    """

    cycle_resources = get_cycle_resources(db, cycle_id)

    if not cycle_resources:
        return {
            "cycle_id": cycle_id,
            "overall_utilization_rate": Decimal("0.00"),
            "total_raw_materials_consumed": Decimal("0"),
            "total_labor_hours_used": Decimal("0"),
            "total_labor_hours_capacity": Decimal("0"),
            "total_machine_hours_used": Decimal("0"),
            "total_machine_hours_capacity": Decimal("0"),
            "material_resource_count": 0,
            "most_constrained_resource": None,
            "at_risk_resources": [],
            "resources": [],
            "bottlenecks": [],
        }

    consumption_by_resource = {
        item["resource_id"]: item["required_quantity"]
        for item in calculate_resource_consumption(db, cycle_id)
    }

    resource_ids = [
        cycle_resource.resource_id
        for cycle_resource in cycle_resources
    ]

    resources_statement = select(Resource).where(
        Resource.id.in_(resource_ids)
    )

    resources_by_id = {
        resource.id: resource
        for resource in db.scalars(resources_statement).all()
    }

    resources = []
    bottlenecks = []
    at_risk_resources = []
    most_constrained_resource = None

    total_consumed = Decimal("0")
    total_available = Decimal("0")
    total_raw_materials_consumed = Decimal("0")
    total_labor_hours_used = Decimal("0")
    total_labor_hours_capacity = Decimal("0")
    total_machine_hours_used = Decimal("0")
    total_machine_hours_capacity = Decimal("0")
    material_resource_count = 0

    for cycle_resource in cycle_resources:
        resource = resources_by_id.get(cycle_resource.resource_id)

        if resource is None:
            continue

        consumed_quantity = consumption_by_resource.get(
            cycle_resource.resource_id,
            Decimal("0"),
        )

        available_quantity = cycle_resource.available_quantity
        remaining_quantity = available_quantity - consumed_quantity

        if available_quantity > 0:
            utilization_rate = (
                consumed_quantity
                / available_quantity
                * Decimal("100")
            ).quantize(Decimal("0.01"))
        else:
            utilization_rate = Decimal("0.00")

        category = _classify_resource_type(resource.resource_type)

        if category == "labor":
            total_labor_hours_used += consumed_quantity
            total_labor_hours_capacity += available_quantity
        elif category == "machine":
            total_machine_hours_used += consumed_quantity
            total_machine_hours_capacity += available_quantity
        else:
            total_raw_materials_consumed += consumed_quantity
            material_resource_count += 1

        total_consumed += consumed_quantity
        total_available += available_quantity

        status = classify_utilization_status(utilization_rate)

        resource_item = {
            "resource_id": resource.id,
            "resource_name": resource.name,
            "resource_type": resource.resource_type,
            "unit": resource.unit,
            "available_quantity": available_quantity,
            "consumed_quantity": consumed_quantity,
            "remaining_quantity": remaining_quantity,
            "utilization_rate": utilization_rate,
            "status": status,
        }

        resources.append(resource_item)

        if status == "at_risk":
            at_risk_resources.append(resource_item)

        if (
            most_constrained_resource is None
            or utilization_rate
            > most_constrained_resource["utilization_rate"]
        ):
            most_constrained_resource = resource_item

        if remaining_quantity <= BOTTLENECK_REMAINING_THRESHOLD:
            bottlenecks.append(
                {
                    "resource_id": resource.id,
                    "resource_name": resource.name,
                    "unit": resource.unit,
                    "remaining_quantity": remaining_quantity,
                    "is_binding": remaining_quantity == Decimal("0"),
                    "shortage_quantity": (
                        abs(remaining_quantity)
                        if remaining_quantity < Decimal("0")
                        else Decimal("0")
                    ),
                }
            )

    if total_available > 0:
        overall_utilization_rate = (
            total_consumed
            / total_available
            * Decimal("100")
        ).quantize(Decimal("0.01"))
    else:
        overall_utilization_rate = Decimal("0.00")

    return {
        "cycle_id": cycle_id,
        # Retained for backward compatibility (blends incompatible
        # units - kg + hours + pcs - into one ratio/count, so neither
        # is meaningful on its own). See most_constrained_resource and
        # material_resource_count below for the unit-safe replacements
        # the frontend now displays instead.
        "overall_utilization_rate": overall_utilization_rate,
        "total_raw_materials_consumed": total_raw_materials_consumed,
        "total_labor_hours_used": total_labor_hours_used,
        "total_labor_hours_capacity": total_labor_hours_capacity,
        "total_machine_hours_used": total_machine_hours_used,
        "total_machine_hours_capacity": total_machine_hours_capacity,
        "material_resource_count": material_resource_count,
        "most_constrained_resource": most_constrained_resource,
        "at_risk_resources": at_risk_resources,
        "resources": resources,
        "bottlenecks": bottlenecks,
    }
