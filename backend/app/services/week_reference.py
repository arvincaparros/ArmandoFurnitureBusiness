"""
Pure, read-only comparison between the actual ILP solver
(app.services.optimization.solve_optimization, unmodified) and the
official "weekly data references.xlsx" workbook (Week 1-8). Never
touches a database session, never writes to products/resources/
cycle_resources, and never feeds an expected quantity into the
solver - comparison against the Excel reference happens only AFTER
solving.
"""
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.data.week_reference_catalog import (
    CATALOG_PRODUCT_KEYS,
    CATALOG_PRODUCTS,
    CATALOG_REQUIREMENTS,
    CATALOG_RESOURCES,
    CATALOG_RESOURCE_UNIT_PRICES,
)
from app.services.optimization import solve_optimization

_REFERENCE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "week_references.json"
)

EXACT_MATCH = "EXACT_MATCH"
MODIFIED_INPUT = "MODIFIED_INPUT"
REFERENCE_INPUT_MISMATCH = "REFERENCE_INPUT_MISMATCH"

# Same magnitude of Excel-side rounding noise established across every
# one of the 8 weeks in the Week 1-8 reconstruction investigation
# (consistently ~P0.3-0.4 out of >P86,000) - never a sign of a real
# input mismatch at this size.
_PROFIT_ROUNDING_TOLERANCE = Decimal("0.50")


class WeekReferenceNotFoundError(Exception):
    pass


class WeekReferenceInfeasibleError(Exception):
    """
    Raised when the actual solver reports Infeasible/Unbounded/any
    non-Optimal status for the given resources - surfaced by the
    router as a clear 400 error, never silently swallowed and never
    papered over with an invented result.
    """


@dataclass
class _CycleResourceInput:
    id: int
    resource_id: int
    available_quantity: Decimal
    unit_price: Decimal
    resource: object


def _load_reference_data() -> dict:
    return json.loads(_REFERENCE_PATH.read_text())


def _resource_keys_with_solver_rows(data: dict) -> list[str]:
    # "laborers" has an availability figure in the workbook but is not
    # one of CATALOG_RESOURCES - it was never a solver-constrained
    # resource (see the Week 1-8 reconstruction investigation), so it
    # is reported to the caller but never turned into a CycleResource.
    return [
        key for key in data["resource_order"]
        if key in CATALOG_RESOURCES
    ]


def _require_week(data: dict, week: int) -> dict:
    week_data = data["weeks"].get(str(week))

    if week_data is None:
        raise WeekReferenceNotFoundError(
            f"No reference data for week {week} (valid range: 1-8)"
        )

    return week_data


def list_week_reference_summaries() -> list[dict]:
    data = _load_reference_data()
    summaries = []

    for week_str, week_data in sorted(
        data["weeks"].items(), key=lambda item: int(item[0])
    ):
        resources = {
            key: {
                "available": Decimal(str(week_data["resources"][key]["available"])),
                "consumed": (
                    Decimal(str(week_data["resources"][key]["consumed"]))
                    if week_data["resources"][key]["consumed"] is not None
                    else None
                ),
                "unit": data["resource_units"][key],
                "name": data["resource_names"][key],
            }
            for key in data["resource_order"]
        }

        summaries.append({
            "week": int(week_str),
            "is_verified": week_data["is_verified"],
            "resources": resources,
            "reference_allocation": dict(week_data["allocation"]),
            "reference_total": sum(week_data["allocation"].values()),
            "reference_profit": Decimal(str(week_data["total_profit"])),
        })

    return summaries


def _resource_usage(
    computed_allocation: dict[str, int],
    resources_used: dict[str, Decimal],
    resource_keys: list[str],
) -> dict[str, dict]:
    """
    Available/Consumed/Remaining/Utilization% per resource, derived
    from the ACTUAL computed allocation and the real BOM - never a
    stale snapshot and never forced to display 100% for every
    resource regardless of what was actually produced.
    """

    quantity_by_catalog_product_id = {
        CATALOG_PRODUCTS[index].id: computed_allocation[key]
        for index, key in enumerate(CATALOG_PRODUCT_KEYS)
    }

    consumed_by_resource_key: dict[str, Decimal] = {
        key: Decimal("0") for key in resource_keys
    }
    resource_id_to_key = {
        CATALOG_RESOURCES[key].id: key for key in resource_keys
    }

    for requirement, resource in CATALOG_REQUIREMENTS:
        key = resource_id_to_key.get(resource.id)

        if key is None:
            continue

        quantity_produced = quantity_by_catalog_product_id.get(
            requirement.product_id, 0
        )

        consumed_by_resource_key[key] += (
            requirement.quantity_required * Decimal(str(quantity_produced))
        )

    usage = {}

    for key in resource_keys:
        available = resources_used[key]
        consumed = consumed_by_resource_key[key]
        remaining = available - consumed
        utilization_rate = (
            (consumed / available * Decimal("100"))
            if available > 0
            else Decimal("0")
        )

        usage[key] = {
            "available": available,
            "consumed": consumed,
            "remaining": remaining,
            "utilization_rate": utilization_rate.quantize(Decimal("0.01")),
        }

    return usage


def compare_week_reference(
    week: int,
    resource_overrides: dict[str, Decimal] | None = None,
) -> dict:
    data = _load_reference_data()
    week_data = _require_week(data, week)
    overrides = resource_overrides or {}
    resource_keys = _resource_keys_with_solver_rows(data)

    resources_used: dict[str, Decimal] = {}
    cycle_resources = []

    for index, key in enumerate(resource_keys):
        historical_value = Decimal(str(week_data["resources"][key]["available"]))
        value = overrides.get(key, historical_value)
        resources_used[key] = value

        catalog_resource = CATALOG_RESOURCES[key]
        cycle_resources.append(
            _CycleResourceInput(
                id=index,
                resource_id=catalog_resource.id,
                available_quantity=value,
                unit_price=CATALOG_RESOURCE_UNIT_PRICES[key],
                resource=catalog_resource,
            )
        )

    is_modified_input = any(
        key in overrides
        and overrides[key]
        != Decimal(str(week_data["resources"][key]["available"]))
        for key in overrides
    )

    try:
        result = solve_optimization(
            cycle_id=week,
            products=CATALOG_PRODUCTS,
            cycle_resources=cycle_resources,
            requirements=CATALOG_REQUIREMENTS,
            forecast=None,
        )
    except ValueError as exc:
        raise WeekReferenceInfeasibleError(str(exc)) from exc

    product_key_by_id = {
        catalog_product.id: key
        for key, catalog_product in zip(CATALOG_PRODUCT_KEYS, CATALOG_PRODUCTS)
    }

    computed_allocation = {
        product_key_by_id[allocation["product_id"]]: allocation["quantity"]
        for allocation in result["allocations"]
    }
    reference_allocation = {
        key: int(value) for key, value in week_data["allocation"].items()
    }

    computed_profit = Decimal(str(result["objective_value"]))
    reference_profit = Decimal(str(week_data["total_profit"]))

    allocation_matches_reference = computed_allocation == reference_allocation
    profit_matches_reference = (
        abs(computed_profit - reference_profit) <= _PROFIT_ROUNDING_TOLERANCE
    )

    if is_modified_input:
        reference_match_status = MODIFIED_INPUT
    elif allocation_matches_reference and profit_matches_reference:
        reference_match_status = EXACT_MATCH
    else:
        # Reference resources were used unmodified, yet the result
        # still disagrees with the Excel - never reported as an exact
        # match in this case, so a real discrepancy is never masked.
        reference_match_status = REFERENCE_INPUT_MISMATCH

    allocation_difference = {
        key: computed_allocation.get(key, 0) - reference_allocation.get(key, 0)
        for key in CATALOG_PRODUCT_KEYS
    }

    return {
        "week": week,
        "is_modified_input": is_modified_input,
        "reference_match_status": reference_match_status,
        "resources_used": resources_used,
        "resource_usage": _resource_usage(
            computed_allocation, resources_used, resource_keys
        ),
        "status": result["status"],
        "computed_allocation": computed_allocation,
        "reference_allocation": reference_allocation,
        "allocation_difference": allocation_difference,
        "allocation_matches_reference": allocation_matches_reference,
        "computed_total": sum(computed_allocation.values()),
        "reference_total": sum(reference_allocation.values()),
        "computed_profit": computed_profit,
        "reference_profit": reference_profit,
        "profit_matches_reference": profit_matches_reference,
    }
