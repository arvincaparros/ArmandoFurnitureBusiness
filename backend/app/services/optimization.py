from datetime import datetime
from decimal import Decimal

import pulp

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CycleResource,
    Product,
    ProductResourceRequirement,
    ProductionAllocation,
    ProductionCycle,
    Resource,
)
from app.services.optimization_history import (
    get_latest_optimization_history_run,
)
from app.services.production_application import (
    get_cycle_consumed_by_resource,
    has_application_for_run,
    save_production_application,
)
from app.services.production_calculation import (
    BOTTLENECK_REMAINING_THRESHOLD,
    calculate_resource_requirements_for_quantities,
)
from app.services.resource_utilization import (
    calculate_resource_utilization,
)
from app.services.resource_utilization_history import (
    save_resource_utilization_history,
)

def _is_labor_resource(resource: Resource) -> bool:
    # Matches resource_utilization.py's _classify_resource_type() and
    # cycle_resource.py's _requires_positive_unit_price() - kept as
    # its own local copy rather than imported from either: both are
    # private (leading-underscore) helpers not meant for cross-module
    # use, and this module only ever needs a plain labor/non-labor
    # check, not resource_utilization.py's fuller
    # labor/machine/material classification.
    return resource.resource_type.strip().lower() == "labor"


def get_optimization_data(
    db: Session,
    cycle_id: int,
) -> dict:
    """
    Load products, resource requirements, and available
    cycle resources needed by the optimization model.
    """

    # Determinism fix: ordered explicitly, like products_statement
    # below already was - without this, Postgres does not guarantee
    # row order for a query with no ORDER BY, so the ILP model built
    # from these rows (variable/constraint insertion order) could
    # differ between two Generate calls with otherwise identical
    # inputs, which is exactly the kind of difference that can select
    # a different tied-optimal solution. Ordered by id (insertion
    # order), not resource_id, so it stays stable even if a resource
    # is swapped out for another on the same cycle.
    cycle_resources_statement = select(
        CycleResource
    ).where(
        CycleResource.production_cycle_id == cycle_id
    ).order_by(
        CycleResource.id
    )

    cycle_resources = db.scalars(
        cycle_resources_statement
    ).all()

    resource_ids = [
        cycle_resource.resource_id
        for cycle_resource in cycle_resources
    ]

    if not resource_ids:
        return {
            "cycle_resources": [],
            "products": [],
            "requirements": [],
        }

    # Determinism fix: same reasoning as cycle_resources_statement
    # above - ordered by id so the ILP's constraint-building loops
    # (add_resource_constraints, calculate_unit_profit, etc.) see
    # these rows in a stable, repeatable order across Generate calls.
    requirements_statement = (
        select(
            ProductResourceRequirement,
            Resource,
        )
        .join(
            Resource,
            Resource.id
            == ProductResourceRequirement.resource_id,
        )
        .where(
            ProductResourceRequirement.resource_id.in_(
                resource_ids
            )
        )
        .order_by(
            ProductResourceRequirement.id
        )
    )

    requirements = db.execute(
        requirements_statement
    ).all()

    product_ids = list(
        {
            requirement.product_id
            for requirement, _resource in requirements
        }
    )

    if not product_ids:
        return {
            "cycle_resources": cycle_resources,
            "products": [],
            "requirements": requirements,
        }

    products_statement = (
        select(Product)
        .where(
            Product.id.in_(product_ids),
            Product.is_active.is_(True),
        )
        .order_by(Product.id)
    )

    products = db.scalars(
        products_statement
    ).all()

    return {
        "cycle_resources": cycle_resources,
        "products": products,
        "requirements": requirements,
    }

def create_decision_variables(
    products,
) -> dict[int, pulp.LpVariable]:
    """
    Create one integer decision variable for each active product,
    floored at that product's own minimum_demand (never a flat 0) -
    a hard ILP requirement: if resources/forecast can't support every
    product's minimum simultaneously, the whole plan must come back
    Infeasible rather than silently under-producing one product.

    Used only by the Phase 1 (hard-minimum) solve path - see
    solve_optimization/_is_minimum_demand_vector_feasible. The Phase 2
    adaptive path (minimum demand infeasible) builds its own variables
    with lowBound=0 at each stage instead, since the whole point of
    that path is that production may legitimately land below
    minimum_demand.

    Read directly off each product's own ORM row - never a
    positional/array mapping (Product.id ordering is incidental, not a
    business contract). `or 0` guards only an unflushed in-memory
    object with no default applied yet; the DB column itself is NOT
    NULL DEFAULT 0.
    """

    variables = {}

    for product in products:
        variables[product.id] = pulp.LpVariable(
            f"product_{product.id}",
            lowBound=float(product.minimum_demand or 0),
            cat="Integer",
        )

    return variables


def validate_minimum_demand_capacity(
    products,
    cycle_resources,
    requirements,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> None:
    """
    Pre-solve check: confirms the exact minimum-demand vector alone
    (every product held at its own minimum, everything else at 0)
    fits inside this cycle's REMAINING resource capacities - available
    minus whatever earlier applications this cycle have already
    consumed (see _remaining_cycle_capacity; None reproduces the
    original full-capacity behavior). That single point is a valid
    feasibility witness for "can every minimum be satisfied
    simultaneously" - resource consumption is strictly additive/
    linear, so if that point already violates a resource cap, no point
    honoring every minimum can exist; if it doesn't, that same point is
    itself feasible. Raised before create_decision_variables/
    problem.solve() ever run, listing every short resource - never a
    single generic "Infeasible" status from the solver for this
    specific, common cause. Never touches the objective or
    calculate_unit_profit.

    An inactive resource is treated as zero available capacity here
    too, matching add_resource_constraints' convention - never its
    stale available_quantity (that would silently treat a soft-deleted
    resource as still fully available).
    """

    minimum_by_product_id = {
        product.id: product.minimum_demand
        for product in products
    }

    required_by_resource: dict[int, Decimal] = {}

    for requirement, _resource in requirements:
        minimum = minimum_by_product_id.get(
            requirement.product_id,
            Decimal("0"),
        )

        if minimum <= 0:
            continue

        required_by_resource[requirement.resource_id] = (
            required_by_resource.get(
                requirement.resource_id,
                Decimal("0"),
            )
            + requirement.quantity_required * minimum
        )

    shortages = []

    for cycle_resource in cycle_resources:
        required = required_by_resource.get(
            cycle_resource.resource_id,
            Decimal("0"),
        )

        available = _remaining_cycle_capacity(
            cycle_resource,
            already_consumed_by_resource_id,
        )

        if required > available:
            resource = cycle_resource.resource

            shortages.append(
                f"{resource.name} (needs {required} {resource.unit}, "
                f"only {available} "
                f"{resource.unit} available)"
            )

    if shortages:
        raise ValueError(
            "Unable to generate a feasible production plan: minimum "
            "demand requires more than is available this cycle for "
            + ", ".join(shortages)
            + "."
        )


def validate_minimum_demand_forecast(
    products,
    forecast: dict[int, Decimal] | None,
) -> None:
    """
    Pre-solve check: `forecast` here is already the router's
    positive-forecast-only dict (see production.py::
    optimize_production) - exactly the set of products that get a
    real x_i <= forecast_i ceiling in add_forecast_constraints(). A
    product with no entry here has no ceiling at all today (existing,
    unchanged behavior) and can never conflict with its minimum.
    """

    if not forecast:
        return

    conflicts = []

    for product in products:
        if product.minimum_demand <= 0:
            continue

        ceiling = forecast.get(product.id)

        if ceiling is not None and product.minimum_demand > ceiling:
            conflicts.append(
                f"{product.name} (minimum demand "
                f"{product.minimum_demand}, forecast ceiling "
                f"{ceiling})"
            )

    if conflicts:
        raise ValueError(
            "Cannot generate a production plan: minimum demand "
            "exceeds the current forecast ceiling for "
            + ", ".join(conflicts)
            + "."
        )


def validate_minimum_demand_resource_availability(
    db: Session,
    cycle_id: int,
) -> None:
    """
    Pre-solve check: for every ACTIVE product this cycle would
    otherwise consider eligible (same "has at least one requirement on
    a resource priced this cycle" rule get_optimization_data() itself
    uses to build its product list - so an unrelated product with no
    connection whatsoever to this cycle's resource universe, e.g. a
    completely different test fixture's products/resources, is never
    pulled in), its COMPLETE ProductResourceRequirement list is
    re-queried directly here - deliberately NOT the `requirements`
    collection get_optimization_data() builds, which silently drops
    any single requirement whose resource lacks a CycleResource row
    this cycle at all.

    Widened (adaptive minimum demand) to cover EVERY eligible product,
    not only ones with minimum_demand > 0: the adaptive optimizer
    (see solve_optimization) now gives a minimum_demand == 0 product a
    real coverage role too (Stage 2), and an unpriced-resource
    requirement silently dropped by get_optimization_data() would
    otherwise let that product look "coverable" when it secretly
    isn't - there would be no actionable error, just an inexplicably
    uncovered product. The error message distinguishes the two cases
    (a stated minimum vs. a coverage-eligible product with no stated
    minimum) so it stays accurate either way. Behavior for a
    minimum_demand > 0 product is unchanged from before this widening.

    Deliberately does NOT raise on an INACTIVE resource - an inactive
    resource is modeled as zero available capacity (see
    add_resource_constraints), so a product that needs it is pushed
    toward 0/shortfall by the ordinary constraint math (Phase 1's
    validate_minimum_demand_capacity, or Phase 2's coverage stages),
    never blocked here. This check instead fires only when a resource
    has genuinely NO CycleResource row for this cycle at all - there's
    no known capacity to model as zero (not even a real zero), so
    unlike the inactive case there's no number available to constrain
    against, and fabricating one would either fabricate free/unlimited
    capacity (if skipped) or an invented quantity (if defaulted to
    something). Labor is exempt from this check entirely - exactly as
    calculate_unit_profit treats it (capacity-constrained via its own
    resource row, but costed from Product.labor_cost, never from a
    CycleResource rate). Raises before the solver runs; never forces
    production against a resource with no pricing data, and never
    treats it as free.
    """

    priced_resource_ids = {
        cycle_resource.resource_id
        for cycle_resource in db.scalars(
            select(CycleResource).where(
                CycleResource.production_cycle_id == cycle_id
            )
        ).all()
    }

    if not priced_resource_ids:
        return

    candidate_product_ids = {
        requirement.product_id
        for requirement in db.scalars(
            select(ProductResourceRequirement).where(
                ProductResourceRequirement.resource_id.in_(
                    priced_resource_ids
                )
            )
        ).all()
    }

    if not candidate_product_ids:
        return

    eligible_products = db.scalars(
        select(Product).where(
            Product.id.in_(candidate_product_ids),
            Product.is_active.is_(True),
        )
    ).all()

    if not eligible_products:
        return

    product_ids = [product.id for product in eligible_products]
    products_by_id = {
        product.id: product for product in eligible_products
    }

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

    issues = []

    for requirement, resource in requirement_rows:
        if _is_labor_resource(resource):
            continue

        if resource.id in priced_resource_ids:
            continue

        product = products_by_id[requirement.product_id]

        if product.minimum_demand and product.minimum_demand > 0:
            issues.append(
                f"{product.name} has a minimum demand of "
                f"{product.minimum_demand} but requires {resource.name}, "
                "which is currently unpriced for this cycle"
            )
        else:
            issues.append(
                f"{product.name} is eligible for production coverage "
                f"but requires {resource.name}, which is currently "
                "unpriced for this cycle"
            )

    if issues:
        raise ValueError(
            "Cannot generate a production plan: "
            + "; ".join(issues)
            + "."
        )

def _remaining_cycle_capacity(
    cycle_resource,
    already_consumed_by_resource_id: dict[int, Decimal] | None,
) -> Decimal:
    """
    What a NEW plan may still draw from this resource this cycle:
    available_quantity minus whatever earlier applications in this
    SAME cycle have already consumed (production_application_resource_
    items, via get_cycle_consumed_by_resource) - never the cycle's
    full original capacity once anything has been applied. Floored at
    zero, matching find_resource_capacity_shortages' identical
    convention on the Apply side, so a resource reduced below what is
    already consumed reads as fully spent, never a negative bound.

    An inactive resource is still modeled as zero capacity first (see
    add_resource_constraints' own note) - already_consumed is only
    ever subtracted from a resource that is actually active.

    `already_consumed_by_resource_id=None` (the default throughout
    this module) reproduces the original, pre-this-fix behavior
    exactly: the full available_quantity, unreduced. This is what the
    very first generation in a cycle - and every existing caller that
    has not been updated to pass this - still gets.
    """

    available_quantity = (
        cycle_resource.available_quantity
        if cycle_resource.resource.is_active
        else Decimal("0")
    )

    consumed = (already_consumed_by_resource_id or {}).get(
        cycle_resource.resource_id,
        Decimal("0"),
    )

    return max(Decimal("0"), available_quantity - consumed)


def _exhausted_resources(
    cycle_resources,
    already_consumed_by_resource_id: dict[int, Decimal] | None,
) -> list[dict]:
    """
    Resources with truly zero (floored) remaining capacity - used to
    explain an all-zero optimization result at Apply time
    (apply_optimization's "no applicable product-level results"
    guard) without guessing at a cause the numbers do not actually
    prove.

    Deliberately narrow: a resource with ANY positive remaining
    capacity is never listed here, even if that is not enough for a
    whole unit of any one product. Reporting it as "limiting" in that
    case would not be provably true - the real bottleneck could be a
    different resource's interaction with a specific product's
    requirement ratio, not this resource's capacity alone - so the
    caller falls back to the existing generic message instead of a
    message this function cannot actually support. This also means an
    all-zero result caused by a conflict with minimum_demand is never
    reported here: that case is already caught earlier, at Generate
    time, by validate_minimum_demand_capacity's own pre-solve check,
    so an OPTIMAL run reaching this guard at all is never a
    minimum-demand conflict - only a genuine capacity shortage.
    """

    exhausted = []

    for cycle_resource in cycle_resources:
        remaining = _remaining_cycle_capacity(
            cycle_resource,
            already_consumed_by_resource_id,
        )

        if remaining <= Decimal("0"):
            exhausted.append(
                {
                    "resource_name": cycle_resource.resource.name,
                    "unit": cycle_resource.resource.unit,
                }
            )

    return exhausted


def add_resource_constraints(
    problem: pulp.LpProblem,
    variables: dict[int, pulp.LpVariable],
    cycle_resources,
    requirements,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> None:
    """
    Add one resource constraint for each resource available
    in the production cycle.

    Total resource consumption must not exceed the REMAINING
    available quantity - available_quantity minus whatever earlier
    applications in this same cycle have already consumed (see
    _remaining_cycle_capacity). This is what makes Generate consistent
    with Apply: apply_optimization has validated proposals against
    exactly this same remaining-capacity figure
    (get_cycle_consumed_by_resource) since the ledger was introduced;
    Generate now solves against it too, instead of the cycle's full
    original capacity every time.
    """

    requirements_by_resource: dict[
        int,
        list[tuple[int, Decimal]],
    ] = {}

    for requirement, resource in requirements:
        requirements_by_resource.setdefault(
            requirement.resource_id,
            [],
        ).append(
            (
                requirement.product_id,
                requirement.quantity_required,
            )
        )

    for cycle_resource in cycle_resources:
        resource_id = cycle_resource.resource_id

        # An inactive resource is modeled as having zero available
        # capacity this cycle - never its stale available_quantity
        # (that would silently treat a soft-deleted resource as still
        # fully available, see resource_utilization.py's own note on
        # this), and never left unconstrained either (that would
        # fabricate unlimited capacity). If a product's minimum demand
        # needs a positive amount of it, validate_minimum_demand_
        # capacity catches that pre-solve as an ordinary capacity
        # shortage naming this same resource; if the product has no
        # minimum demand, it's simply pushed toward 0 for its own
        # production here, same as any other capacity shortage.
        available_quantity = _remaining_cycle_capacity(
            cycle_resource,
            already_consumed_by_resource_id,
        )

        resource_requirements = requirements_by_resource.get(
            resource_id,
            []
        )

        consumption = pulp.lpSum(
            variables[product_id] * float(quantity_required)
            for product_id, quantity_required
            in resource_requirements
            if product_id in variables
        )

        problem += (
            consumption <= float(available_quantity),
            f"resource_{resource_id}_limit",
        )

def calculate_unit_profit(
    product,
    requirements,
    cycle_resources,
) -> Decimal:
    """
    Calculate the profit for producing one unit
    of a product.

    Profit = selling price - resource costs - labor cost.

    Labor is deliberately excluded from the resource-price loop
    below and costed from product.labor_cost instead: the client's
    cost model proves labor cost varies per product independent of
    labor hours (two products with identical hours and identical BOM
    can have different total cost) - it is not
    labor_hours x a shared CycleResource rate. Labor hours themselves
    are unaffected and still count toward the Labor resource's
    capacity constraint in add_resource_constraints() - only the cost
    contribution changes here.
    """

    cycle_resource_prices = {
        cycle_resource.resource_id: cycle_resource.unit_price
        for cycle_resource in cycle_resources
    }

    total_resource_cost = Decimal("0")

    for requirement, resource in requirements:
        if requirement.product_id != product.id:
            continue

        if _is_labor_resource(resource):
            continue

        unit_price = cycle_resource_prices.get(
            requirement.resource_id
        )

        if unit_price is None:
            continue

        total_resource_cost += (
            requirement.quantity_required
            * unit_price
        )

    total_resource_cost += product.labor_cost

    return (
        product.selling_price
        - total_resource_cost
    )

def add_profit_objective(
    problem: pulp.LpProblem,
    variables: dict[int, pulp.LpVariable],
    products,
    requirements,
    cycle_resources,
):
    """
    Set the optimization objective to maximize total production
    profit. Returns the profit expression itself, so a caller that
    later needs to lock this exact value in as a floor (see
    _resolve_profit_ties_deterministically) can reuse it directly
    rather than reconstructing an equivalent expression by hand.
    """

    profit_expression = pulp.lpSum(
        variables[product.id]
        * float(
            calculate_unit_profit(
                product,
                requirements,
                cycle_resources,
            )
        )
        for product in products
    )

    problem += profit_expression

    return profit_expression


# Same floating-point-noise tolerance as _FAIRNESS_EPSILON below, kept
# as its own named constant rather than shared: this one guards
# whatever value _lock_primary_objective_and_resolve's caller just
# locked in (a profit, or Stage 3's profit-of-covered-set) carried
# from one solve into the next solve's hard floor - not a fairness
# ratio - same numeric magnitude of noise, different quantities,
# kept conceptually separate.
_DETERMINISM_LOCK_EPSILON = 1e-6

# Deterministic tie-break fallback only (never an actual model bound):
# used solely to size a weight when a product's true upper bound
# cannot be computed from its own requirements (should not happen in
# practice - every product reaching the solver has at least one
# ProductResourceRequirement, by construction of get_optimization_data's
# product selection - this exists purely as a defensive fallback).
_TIE_BREAK_FALLBACK_BOUND = 1_000_000


def _product_quantity_upper_bound(
    product,
    requirements,
    cycle_resources,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None,
) -> int:
    """
    A safe, never-too-small upper bound on how many units of this
    product the model could possibly assign - used only to size the
    deterministic tie-break weights in _assign_tie_break_weights,
    never as an actual constraint on the model itself.

    Computed as if this product had each of its required resources
    entirely to itself, ignoring every other product's competing
    draw on the same pool. That can only overstate the true
    achievable quantity, never understate it - which is the one
    property the weighting scheme actually depends on (an
    underestimate here could let a lower-priority product's weighted
    contribution exceed a higher-priority one's, breaking the
    intended tie-break order).
    """

    cycle_resource_by_id = {
        cycle_resource.resource_id: cycle_resource
        for cycle_resource in cycle_resources
    }

    bounds = []

    for requirement, _resource in requirements:
        if requirement.product_id != product.id:
            continue

        if requirement.quantity_required <= 0:
            continue

        cycle_resource = cycle_resource_by_id.get(
            requirement.resource_id
        )

        if cycle_resource is None:
            bounds.append(0)
            continue

        remaining = _remaining_cycle_capacity(
            cycle_resource,
            already_consumed_by_resource_id,
        )

        bounds.append(
            int(remaining // requirement.quantity_required)
        )

    if forecast is not None:
        ceiling = forecast.get(product.id)

        if ceiling is not None:
            bounds.append(int(ceiling))

    if not bounds:
        return _TIE_BREAK_FALLBACK_BOUND

    return max(0, min(bounds))


def _weights_from_bounds(
    ordered_products,
    bounds_by_id: dict[int, int],
) -> dict[int, int]:
    """
    Shared recursive core of the documented, stable tie-break rule
    (approved business requirement): among every solution that
    achieves the same locked primary value, prefer the one that
    favors the LOWEST product_id as much as possible; among whatever
    that leaves undecided, prefer the next-lowest product_id, and so
    on. `ordered_products` must already be sorted ascending by id.

    Each product's weight, assigned from the highest id backward, is
    built to strictly exceed the combined maximum possible
    contribution of every lower-priority (higher-id) product's
    weighted term (using `bounds_by_id` as each product's own true
    upper bound on its term). That guarantees true lexicographic
    preference by ascending id - gaining even one unit of a
    higher-priority product's term always outweighs any combination
    of lower-priority ones - not merely an approximation of it.

    Limitation: the weights grow with the product of per-product
    bounds, so with very many products and/or very large per-product
    bounds at the same time, the largest weight could exceed what the
    solver's underlying double-precision arithmetic represents
    exactly. This is safe for realistic furniture-catalog sizes
    (comfortably so for the double-digit product counts this
    application targets, and exact for a binary 0/1 bound - see
    _assign_binary_tie_break_weights - up to roughly 50 products).
    It never risks the locked primary value itself - that is enforced
    by a hard constraint in _lock_primary_objective_and_resolve, not
    by this objective - the only possible effect in that edge case is
    an imprecise tie-break choice, never a wrong primary value.
    """

    weights: dict[int, int] = {}
    cumulative_lower_priority_contribution = 0

    for product in reversed(ordered_products):
        weight = cumulative_lower_priority_contribution + 1
        weights[product.id] = weight
        cumulative_lower_priority_contribution += (
            bounds_by_id[product.id] * weight
        )

    return weights


def _assign_tie_break_weights(
    products,
    requirements,
    cycle_resources,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None,
) -> dict[int, int]:
    """
    _weights_from_bounds specialized for an open-ended INTEGER
    quantity decision (Phase 1's single solve, Stage 5) - each
    product's bound is its own true resource/forecast-derived upper
    bound (_product_quantity_upper_bound), since an open quantity
    variable's term can range anywhere up to that.
    """

    ordered_products = sorted(
        products,
        key=lambda product: product.id,
    )

    bounds_by_id = {
        product.id: _product_quantity_upper_bound(
            product,
            requirements,
            cycle_resources,
            forecast,
            already_consumed_by_resource_id,
        )
        for product in ordered_products
    }

    return _weights_from_bounds(ordered_products, bounds_by_id)


def _assign_binary_tie_break_weights(
    products,
) -> dict[int, int]:
    """
    _weights_from_bounds specialized for a BINARY coverage decision
    (Stage 3) - each product's own term is 0 or 1, so its bound is
    trivially 1, and the general recursive formula degenerates
    exactly to the classic "prefer the lower-indexed binary choice"
    power-of-two weighting (1, 2, 4, 8, ...) - exact for any
    realistic product catalog (comfortably within double-precision's
    exact integer range for up to roughly 50 products).
    """

    ordered_products = sorted(
        products,
        key=lambda product: product.id,
    )

    bounds_by_id = {
        product.id: 1
        for product in ordered_products
    }

    return _weights_from_bounds(ordered_products, bounds_by_id)


def _lock_primary_objective_and_resolve(
    problem: pulp.LpProblem,
    primary_expression,
    tie_break_expression,
    stage_name: str,
) -> float:
    """
    The generic two-stage determinism mechanism (approved business
    requirement): `problem` has just been solved to Optimal with
    `primary_expression` as its objective. This locks that exact
    value in as a hard floor (never a ceiling - nothing above it was
    ever feasible under the constraints already in `problem`, so this
    can only pin the value, never reduce it - satisfying "never let
    the secondary objective reduce the primary value" structurally,
    not just by convention) and re-solves for `tie_break_expression`
    instead, so that whenever more than one solution shares the
    primary value, every Generate run with the same inputs picks the
    SAME one.

    A no-op in effect whenever the primary-maximizing (or minimizing)
    solution is already unique: the floor constraint then leaves
    exactly one feasible point, and this second solve simply
    re-confirms it.

    Returns the locked primary value - the caller must report THIS,
    never problem.objective.value() after this function returns (the
    objective has been replaced by `tie_break_expression` by then).
    """

    locked_value = problem.objective.value()

    problem += (
        primary_expression
        >= locked_value - _DETERMINISM_LOCK_EPSILON,
        f"{stage_name}_primary_floor",
    )

    problem.setObjective(tie_break_expression)

    _solve_stage_or_raise(
        problem,
        f"{stage_name} (deterministic tie-break)",
    )

    return locked_value


def _resolve_profit_ties_deterministically(
    problem: pulp.LpProblem,
    products,
    requirements,
    cycle_resources,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None,
    variables: dict[int, pulp.LpVariable],
    profit_expression,
    stage_name: str,
) -> float:
    """
    Phase 1's single solve / Stage 5's tie-break: profit is the
    primary value, the ascending-id quantity weights
    (_assign_tie_break_weights) are the tie-break. See
    _lock_primary_objective_and_resolve for the shared mechanism.
    """

    weights = _assign_tie_break_weights(
        products,
        requirements,
        cycle_resources,
        forecast,
        already_consumed_by_resource_id,
    )

    tie_break_expression = pulp.lpSum(
        variables[product.id] * weights[product.id]
        for product in products
    )

    return _lock_primary_objective_and_resolve(
        problem,
        profit_expression,
        tie_break_expression,
        stage_name,
    )


def _resolve_coverage_ties_deterministically(
    problem: pulp.LpProblem,
    products,
    coverage_variables: dict[int, pulp.LpVariable],
    profit_of_covered_expression,
    stage_name: str,
) -> float:
    """
    Stage 3's tie-break: total profit of the covered set (at 1 unit
    each) is the primary value, the ascending-id BINARY weights
    (_assign_binary_tie_break_weights) are the tie-break - preferring,
    among every coverage pattern that ties on profitability, the one
    that covers the lowest product_id(s) it can. See
    _lock_primary_objective_and_resolve for the shared mechanism.
    """

    weights = _assign_binary_tie_break_weights(products)

    tie_break_expression = pulp.lpSum(
        coverage_variables[product.id] * weights[product.id]
        for product in products
    )

    return _lock_primary_objective_and_resolve(
        problem,
        profit_of_covered_expression,
        tie_break_expression,
        stage_name,
    )

def _is_minimum_demand_vector_feasible(
    products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> bool:
    """
    Phase 1/2 branch decision for solve_optimization. Reuses
    validate_minimum_demand_capacity/validate_minimum_demand_forecast
    completely unchanged as a non-raising feasibility witness: if
    either would raise (the exact minimum-demand vector doesn't fit
    this cycle's REMAINING resource capacities, or conflicts with a
    forecast ceiling), the full vector cannot be satisfied
    simultaneously, and Phase 2 (adaptive) takes over. Deliberately
    does not call validate_minimum_demand_resource_availability - that
    check is a data-completeness gate (a resource with no
    CycleResource row at all this cycle), not a capacity/forecast
    feasibility question, and already runs unconditionally from the
    router before solve_optimization is ever called.
    """

    try:
        validate_minimum_demand_capacity(
            products,
            cycle_resources,
            requirements,
            already_consumed_by_resource_id,
        )
        validate_minimum_demand_forecast(
            products,
            forecast,
        )
    except ValueError:
        return False

    return True


def _round_to_int(value, default: int = 0) -> int:
    """
    Every count/value carried from one lexicographic stage into the
    next is rounded explicitly before use as a bound - CBC's reported
    objective/variable values can land a hair off an exact integer
    (e.g. 1.9999999998) even when the true optimal solution is
    integral, and an un-rounded value used directly as a `>=`/`<=`
    bound in the next stage could make that next stage spuriously
    infeasible-by-a-rounding-hair.
    """

    if value is None:
        return default

    return int(round(value))


def _solve_stage_or_raise(
    problem: pulp.LpProblem,
    stage_name: str,
) -> None:
    # threads=1 is made explicit here (CBC already defaults to single-
    # threaded when PuLP is not told otherwise, but an un-stated
    # default is still a determinism risk if that default ever
    # changes in a future CBC/PuLP version) - every stage of the
    # adaptive model, and the deterministic tie-break re-solve, goes
    # through this one function, so this single call site is enough
    # to cover all of them consistently.
    problem.solve(
        pulp.PULP_CBC_CMD(msg=False, threads=1)
    )

    status = pulp.LpStatus[problem.status]

    if status != "Optimal":
        raise ValueError(
            f"{stage_name} failed with solver status: {status}"
        )


def _partition_by_minimum_demand(products):
    """
    I+ / I0 from the approved mathematical formulation - products with
    a positive original minimum_demand vs. everything else. A product
    with minimum_demand == 0 (or an unflushed None - see
    create_decision_variables' own note on this) is always in I0,
    never I+.
    """

    positive = [
        product
        for product in products
        if (product.minimum_demand or Decimal("0")) > 0
    ]

    zero = [
        product
        for product in products
        if not (product.minimum_demand or Decimal("0")) > 0
    ]

    return positive, zero


def _solve_stage1_positive_minimum_coverage(
    cycle_id: int,
    products,
    positive_products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> int:
    """
    Stage 1 of the approved five-stage lexicographic model: maximize
    the number of positive-minimum-demand products reaching a
    production quantity of at least 1 unit - zero-minimum products
    have no coverage variable here at all, so they structurally cannot
    trade off against a positive-minimum product's coverage (strict
    priority, not a weighted sum).
    """

    problem = pulp.LpProblem(
        f"adaptive_stage1_coverage_{cycle_id}",
        pulp.LpMaximize,
    )

    variables = {
        product.id: pulp.LpVariable(
            f"product_{product.id}",
            lowBound=0,
            cat="Integer",
        )
        for product in products
    }

    add_resource_constraints(
        problem,
        variables,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )

    if forecast is not None:
        add_forecast_constraints(
            problem,
            variables,
            forecast,
        )

    coverage_variables = {
        product.id: pulp.LpVariable(
            f"covered_{product.id}",
            cat="Binary",
        )
        for product in positive_products
    }

    for product in positive_products:
        problem += (
            coverage_variables[product.id] <= variables[product.id],
            f"coverage_link_{product.id}",
        )

    problem += pulp.lpSum(coverage_variables.values())

    _solve_stage_or_raise(problem, "Stage 1 (positive-minimum coverage)")

    return _round_to_int(pulp.value(problem.objective))


def _solve_stage2_total_coverage(
    cycle_id: int,
    products,
    positive_products,
    p1_star: int,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> int:
    """
    Stage 2: without reducing Stage 1's achieved positive-minimum
    coverage count, maximize total coverage across every eligible
    product, including minimum_demand == 0 products. No profit term
    anywhere in this objective - Stage 3 is the only place
    profitability enters the coverage decision.
    """

    problem = pulp.LpProblem(
        f"adaptive_stage2_coverage_{cycle_id}",
        pulp.LpMaximize,
    )

    variables = {
        product.id: pulp.LpVariable(
            f"product_{product.id}",
            lowBound=0,
            cat="Integer",
        )
        for product in products
    }

    add_resource_constraints(
        problem,
        variables,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )

    if forecast is not None:
        add_forecast_constraints(
            problem,
            variables,
            forecast,
        )

    coverage_variables = {
        product.id: pulp.LpVariable(
            f"covered_{product.id}",
            cat="Binary",
        )
        for product in products
    }

    for product in products:
        problem += (
            coverage_variables[product.id] <= variables[product.id],
            f"coverage_link_{product.id}",
        )

    if positive_products:
        problem += (
            pulp.lpSum(
                coverage_variables[product.id]
                for product in positive_products
            )
            >= p1_star,
            "positive_minimum_coverage_floor",
        )

    problem += pulp.lpSum(coverage_variables.values())

    _solve_stage_or_raise(problem, "Stage 2 (total coverage)")

    return _round_to_int(pulp.value(problem.objective))


def _solve_stage3_profitability_tiebreak(
    cycle_id: int,
    products,
    positive_products,
    p1_star: int,
    p2_star: int,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> set[int]:
    """
    Stage 3: among every coverage pattern achieving (p1_star, p2_star),
    pick the one maximizing total profit AT exactly 1 unit per covered
    product - unit profit (calculate_unit_profit) is a constant per
    product, independent of quantity, so this is an exact, well-defined
    ranking using only the binary coverage pattern, never a quantity.

    The decision variables here ARE the coverage indicators themselves
    (reused directly as add_resource_constraints/add_forecast_constraints'
    `variables` dict - both functions only need a dict[product_id,
    LpVariable] and never inspect its `cat`, so a Binary variable
    standing in for "quantity" here is exactly equivalent to the
    plan's `x_i = y_i` pinning, without a redundant second variable).

    Determinism fix: unlike Stages 1/2/4 (each returns only a scalar
    count/ratio, unique by definition even when the underlying
    assignment achieving it is not), this stage returns the actual
    covered_ids SET - an identity-level decision that Stage 4's
    shortfall targets and Stage 5's lower bounds both depend on
    directly. If more than one coverage pattern ties on profitability,
    _resolve_coverage_ties_deterministically locks that exact profit
    in and re-solves for the documented ascending-product-id
    tie-break, so the SAME pattern is chosen every time.

    Returns ONLY the resulting covered-product-id set - no quantity
    value from this stage is ever read by any later stage. This is
    deliberate: Stage 3 decides WHO is guaranteed coverage, never HOW
    MUCH anyone (covered or not) ultimately produces.
    """

    problem = pulp.LpProblem(
        f"adaptive_stage3_tiebreak_{cycle_id}",
        pulp.LpMaximize,
    )

    coverage_variables = {
        product.id: pulp.LpVariable(
            f"covered_{product.id}",
            cat="Binary",
        )
        for product in products
    }

    add_resource_constraints(
        problem,
        coverage_variables,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )

    if forecast is not None:
        add_forecast_constraints(
            problem,
            coverage_variables,
            forecast,
        )

    if positive_products:
        problem += (
            pulp.lpSum(
                coverage_variables[product.id]
                for product in positive_products
            )
            >= p1_star,
            "positive_minimum_coverage_floor",
        )

    problem += (
        pulp.lpSum(coverage_variables.values()) >= p2_star,
        "total_coverage_floor",
    )

    profit_of_covered_expression = pulp.lpSum(
        coverage_variables[product.id]
        * float(
            calculate_unit_profit(
                product,
                requirements,
                cycle_resources,
            )
        )
        for product in products
    )

    problem += profit_of_covered_expression

    _solve_stage_or_raise(
        problem, "Stage 3 (profitability coverage tie-break)"
    )

    _resolve_coverage_ties_deterministically(
        problem,
        products,
        coverage_variables,
        profit_of_covered_expression,
        "adaptive_stage3",
    )

    covered_ids: set[int] = set()

    for product in products:
        value = coverage_variables[product.id].value()

        if value is not None and _round_to_int(value) >= 1:
            covered_ids.add(product.id)

    return covered_ids


def _build_shortfall_ratio_constraints(
    problem: pulp.LpProblem,
    variables: dict[int, pulp.LpVariable],
    shortfall_targets,
) -> dict[int, pulp.LpAffineExpression]:
    """
    Shared by Stages 4 and 5: for every product in shortfall_targets
    (already filtered to the locked-covered, positive-minimum subset -
    I+ ∩ Y* in the approved formulation), define shortfall_i >= 0,
    shortfall_i >= minimum_demand_i - x_i, and return the ratio
    expression shortfall_i / minimum_demand_i keyed by product id -
    minimum_demand_i is a fixed, known-positive constant here (the
    caller only ever passes products with minimum_demand > 0), so
    dividing is a safe, linear scaling, written as multiplication by
    the reciprocal rather than relying on LpAffineExpression.__truediv__
    directly.
    """

    ratios: dict[int, pulp.LpAffineExpression] = {}

    for product in shortfall_targets:
        minimum = float(product.minimum_demand)

        shortfall = pulp.LpVariable(
            f"shortfall_{product.id}",
            lowBound=0,
        )

        problem += (
            shortfall >= minimum - variables[product.id],
            f"shortfall_definition_{product.id}",
        )

        ratios[product.id] = shortfall * (1.0 / minimum)

    return ratios


def _solve_stage4_proportional_fairness(
    cycle_id: int,
    products,
    covered_ids: set[int],
    positive_products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> float:
    """
    Stage 4: with the covered set Y* now fixed (every binary from
    Stage 3 is gone - only the discrete membership set survives),
    minimize the worst-case proportional shortfall among covered,
    positive-minimum products - minimax fairness (not leximin: this
    stage only locks the single worst ratio, Z*; it does not also
    minimize the second-worst, third-worst, etc. among multiple
    Z*-achieving solutions, so Stage 5's profit objective is free to
    reshuffle shortfall among any products that remain tied at Z*
    after this stage). Chosen over a raw sum specifically because a
    sum can concentrate all shortfall on one product as long as the
    total stays low, which is exactly the failure mode the approved
    business rules reject.

    Returns ONLY the scalar Z* - no specific quantity from this stage
    is carried into Stage 5 either, for the same reason Stage 3's
    quantities aren't carried into this one.
    """

    problem = pulp.LpProblem(
        f"adaptive_stage4_fairness_{cycle_id}",
        pulp.LpMinimize,
    )

    variables = {
        product.id: pulp.LpVariable(
            f"product_{product.id}",
            lowBound=(1 if product.id in covered_ids else 0),
            cat="Integer",
        )
        for product in products
    }

    add_resource_constraints(
        problem,
        variables,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )

    if forecast is not None:
        add_forecast_constraints(
            problem,
            variables,
            forecast,
        )

    shortfall_targets = [
        product
        for product in positive_products
        if product.id in covered_ids
    ]

    worst_case = pulp.LpVariable(
        "max_proportional_shortfall",
        lowBound=0,
    )

    ratios = _build_shortfall_ratio_constraints(
        problem,
        variables,
        shortfall_targets,
    )

    for product_id, ratio in ratios.items():
        problem += (
            worst_case >= ratio,
            f"fairness_ratio_cap_{product_id}",
        )

    problem += worst_case

    _solve_stage_or_raise(problem, "Stage 4 (proportional fairness)")

    z_value = pulp.value(worst_case)

    return max(0.0, float(z_value) if z_value is not None else 0.0)


# A RATIO tolerance (shortfall/minimum_demand), not an absolute unit
# tolerance - its absolute slack therefore scales with minimum_demand
# itself (e.g. at minimum_demand=2,000,000 this allows roughly 2 whole
# units past the true Stage 4 cap). Harmless at any realistic
# furniture-production minimum_demand (comfortably under 1 unit of
# slack for any minimum_demand under ~1,000,000), but worth knowing if
# minimum_demand is ever used for a very large quantity.
_FAIRNESS_EPSILON = 1e-6


def _solve_stage5_final_profit(
    cycle_id: int,
    products,
    covered_ids: set[int],
    positive_products,
    z_star: float,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> dict:
    """
    Stage 5: with the fairness ceiling Z* now locked (plus the
    _FAIRNESS_EPSILON tolerance, to absorb Stage 4's own solver
    floating-point noise so this stage can never become
    infeasible-by-a-rounding-hair against Stage 4's exact optimum),
    maximize total profit exactly as add_profit_objective does for the
    Phase 1 hard-minimum path - completely free to allocate any
    remaining capacity to any product, covered or not, since the
    coverage lock is strictly a floor, never a ceiling.
    """

    problem = pulp.LpProblem(
        f"adaptive_stage5_profit_{cycle_id}",
        pulp.LpMaximize,
    )

    variables = {
        product.id: pulp.LpVariable(
            f"product_{product.id}",
            lowBound=(1 if product.id in covered_ids else 0),
            cat="Integer",
        )
        for product in products
    }

    add_resource_constraints(
        problem,
        variables,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )

    if forecast is not None:
        add_forecast_constraints(
            problem,
            variables,
            forecast,
        )

    shortfall_targets = [
        product
        for product in positive_products
        if product.id in covered_ids
    ]

    ratios = _build_shortfall_ratio_constraints(
        problem,
        variables,
        shortfall_targets,
    )

    for product_id, ratio in ratios.items():
        problem += (
            ratio <= z_star + _FAIRNESS_EPSILON,
            f"fairness_ratio_lock_{product_id}",
        )

    profit_expression = add_profit_objective(
        problem,
        variables,
        products,
        requirements,
        cycle_resources,
    )

    _solve_stage_or_raise(problem, "Stage 5 (final profit maximization)")

    # Determinism fix, Stage 2: the solve just above established the
    # maximum achievable profit for this stage. Lock it in and
    # re-solve for a deterministic tie-break among every allocation
    # that shares it - see _resolve_profit_ties_deterministically.
    objective_value = _resolve_profit_ties_deterministically(
        problem,
        products,
        requirements,
        cycle_resources,
        forecast,
        already_consumed_by_resource_id,
        variables,
        profit_expression,
        "adaptive_stage5",
    )

    allocations = []

    for product in products:
        value = variables[product.id].value()
        quantity = _round_to_int(value)

        minimum_demand = product.minimum_demand or Decimal("0")

        shortfall = max(
            Decimal("0"),
            minimum_demand - Decimal(str(quantity)),
        )

        unit_profit = calculate_unit_profit(
            product,
            requirements,
            cycle_resources,
        ).quantize(Decimal("0.0000"))

        total_profit = (
            unit_profit * Decimal(str(quantity))
        ).quantize(Decimal("0.0000"))

        allocations.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_profit": unit_profit,
                "total_profit": total_profit,
                "minimum_demand": minimum_demand,
                "shortfall": shortfall,
            }
        )

    return {
        "status": "Optimal",
        "allocations": allocations,
        # The locked-in profit value from above - NOT problem.
        # objective.value(), which after the tie-break re-solve now
        # holds the secondary (tie-break) objective's value instead.
        "objective_value": objective_value,
    }


def _solve_with_adaptive_minimum_demand(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> dict:
    """
    Phase 2: the full five-stage lexicographic pipeline, run only when
    _is_minimum_demand_vector_feasible has already determined the
    exact original minimum-demand vector cannot be satisfied
    simultaneously. Only four values ever cross a stage boundary -
    p1_star, p2_star, the covered_ids set, and z_star - never a raw
    per-product quantity, by design (see each stage's own docstring).
    """

    positive_products, _zero_products = _partition_by_minimum_demand(
        products
    )

    p1_star = _solve_stage1_positive_minimum_coverage(
        cycle_id,
        products,
        positive_products,
        cycle_resources,
        requirements,
        forecast,
        already_consumed_by_resource_id,
    )

    p2_star = _solve_stage2_total_coverage(
        cycle_id,
        products,
        positive_products,
        p1_star,
        cycle_resources,
        requirements,
        forecast,
        already_consumed_by_resource_id,
    )

    covered_ids = _solve_stage3_profitability_tiebreak(
        cycle_id,
        products,
        positive_products,
        p1_star,
        p2_star,
        cycle_resources,
        requirements,
        forecast,
        already_consumed_by_resource_id,
    )

    z_star = _solve_stage4_proportional_fairness(
        cycle_id,
        products,
        covered_ids,
        positive_products,
        cycle_resources,
        requirements,
        forecast,
        already_consumed_by_resource_id,
    )

    return _solve_stage5_final_profit(
        cycle_id,
        products,
        covered_ids,
        positive_products,
        z_star,
        cycle_resources,
        requirements,
        forecast,
        already_consumed_by_resource_id,
    )


def _solve_with_hard_minimum_demand(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> dict:
    """
    Phase 1: the original, single-solve hard-minimum model - run only
    when _is_minimum_demand_vector_feasible has already confirmed the
    exact original minimum-demand vector fits this cycle's resource
    and forecast constraints simultaneously. Behaviorally identical to
    solve_optimization's entire body before the adaptive feature
    existed; re-running validate_minimum_demand_capacity/
    validate_minimum_demand_forecast here (redundant with the caller's
    own feasibility check, immediately prior) is deliberate - this
    function stays a complete, independently-correct unit exactly as
    it always was, rather than depending on a specific caller to have
    already validated it.
    """

    validate_minimum_demand_capacity(
        products,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )
    validate_minimum_demand_forecast(
        products,
        forecast,
    )

    problem = pulp.LpProblem(
        f"production_optimization_{cycle_id}",
        pulp.LpMaximize,
    )

    variables = create_decision_variables(products)

    add_resource_constraints(
        problem,
        variables,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )

    if forecast is not None:
        add_forecast_constraints(
            problem,
            variables,
            forecast,
        )

    profit_expression = add_profit_objective(
        problem,
        variables,
        products,
        requirements,
        cycle_resources,
    )

    problem.solve(
        pulp.PULP_CBC_CMD(msg=False, threads=1)
    )

    solver_status = pulp.LpStatus[
        problem.status
    ]

    if solver_status == "Infeasible":
        raise ValueError(
            "Production optimization is infeasible with the available resources."
        )

    if solver_status == "Unbounded":
        raise ValueError(
            "Production optimization is unbounded."
        )

    if solver_status != "Optimal":
        raise ValueError(
            f"Production optimization failed with status: {solver_status}"
        )

    # Determinism fix, Stage 2: Stage 1 above just established the
    # maximum achievable profit. Lock it in and re-solve for a
    # deterministic tie-break among every allocation that shares it -
    # see _resolve_profit_ties_deterministically's own docstring.
    objective_value = _resolve_profit_ties_deterministically(
        problem,
        products,
        requirements,
        cycle_resources,
        forecast,
        already_consumed_by_resource_id,
        variables,
        profit_expression,
        "hard_minimum",
    )

    allocations = []

    for product in products:
        quantity = variables[product.id].value()

        if quantity is None:
            quantity = 0

        quantity = int(round(quantity))

        unit_profit = calculate_unit_profit(
            product,
            requirements,
            cycle_resources,
        ).quantize(Decimal("0.0000"))

        total_profit = (
            unit_profit * Decimal(str(quantity))
        ).quantize(Decimal("0.0000"))

        allocations.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_profit": unit_profit,
                "total_profit": total_profit,
                "minimum_demand": product.minimum_demand or Decimal("0"),
                # Hard-floored at minimum_demand via lowBound above (or
                # rejected pre-solve by validate_minimum_demand_capacity/
                # validate_minimum_demand_forecast) - a returned,
                # persisted allocation can never fall short of its own
                # minimum, so shortfall is always 0 here.
                "shortfall": Decimal("0"),
            }
        )

    return {
        "status": solver_status,
        "allocations": allocations,
        # The locked-in Stage 1 profit value - NOT problem.objective.
        # value(), which after the tie-break re-solve above now holds
        # the secondary (tie-break) objective's value, not profit.
        "objective_value": objective_value,
    }


def solve_optimization(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    objective="MAX_PROFIT",
    forecast: dict[int, Decimal] | None = None,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> dict:
    """
    Build and solve the integer linear programming model.

    already_consumed_by_resource_id (see production_application.py::
    get_cycle_consumed_by_resource) makes every resource constraint
    and pre-solve capacity check below INCREMENTAL: this generation
    solves against what is actually LEFT of each resource after
    earlier applications in this same cycle, not the cycle's full
    original capacity every time - the same remaining-capacity figure
    apply_optimization has validated proposals against since the
    ledger was introduced. None (the default - the first generation
    in a cycle, or any caller not yet passing this) reproduces the
    original full-capacity behavior exactly.

    Dispatches between two mutually exclusive solve paths, decided
    once by _is_minimum_demand_vector_feasible:

    Phase 1 (the exact original minimum-demand vector is
    simultaneously feasible): _solve_with_hard_minimum_demand - the
    original, unmodified single-solve model. Every product's quantity
    is hard-floored at its own minimum_demand; profit maximization may
    exceed it, never reduce below it.

    Phase 2 (infeasible): _solve_with_adaptive_minimum_demand - the
    approved five-stage lexicographic model (positive-minimum coverage
    -> total coverage -> profitability coverage tie-break ->
    proportional fairness -> final profit). Never silently forces a
    nonzero quantity where none is feasible; never reduces minimum_demand
    itself (read-only throughout, on the Product row, untouched by
    either path).

    The third minimum-demand check (resource active/priced,
    validate_minimum_demand_resource_availability) is a data-
    completeness gate, not a capacity/forecast feasibility question -
    it runs unconditionally from the router, before this function is
    ever called, regardless of which phase ends up running - see
    production.py::optimize_production.
    """

    if objective != "MAX_PROFIT":
        raise ValueError(
            f"Unsupported optimization objective: {objective}"
        )

    if _is_minimum_demand_vector_feasible(
        products,
        cycle_resources,
        requirements,
        forecast,
        already_consumed_by_resource_id,
    ):
        try:
            return _solve_with_hard_minimum_demand(
                cycle_id,
                products,
                cycle_resources,
                requirements,
                forecast,
                already_consumed_by_resource_id,
            )
        except ValueError:
            # Defense in depth: _is_minimum_demand_vector_feasible's
            # witness check treats minimum_demand as a continuous
            # quantity, but create_decision_variables' lowBound makes
            # it an INTEGER constraint - for a fractional
            # minimum_demand (the column is Numeric(12,4), so this is
            # storable even though every production value today is a
            # whole number), the continuous witness can say "feasible"
            # while the true integer solve is not. Rather than ever
            # surface the old all-or-nothing rejection for a case the
            # feasibility check itself got wrong, fall through to the
            # adaptive path - it has no such gap (every stage solves
            # the real integer problem directly) and is provably
            # always Optimal when any product can be produced at all.
            pass

    return _solve_with_adaptive_minimum_demand(
        cycle_id,
        products,
        cycle_resources,
        requirements,
        forecast,
        already_consumed_by_resource_id,
    )

def build_optimization_result(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    allocations: list[dict],
    status: str,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> dict:
    """
    Build the complete optimization result.

    already_consumed_by_resource_id is forwarded to
    calculate_optimized_resource_usage so the resource_usage it
    returns reflects CUMULATIVE consumption (earlier applications this
    cycle plus `allocations`), not `allocations` alone - see that
    function's docstring. None (the default) reproduces the original
    behavior: usage computed from `allocations` alone, which is what
    apply_optimization's own call still wants for its "what this
    apply just did" response (passing the cumulative figure there
    would double-count this same apply's own allocations, since they
    are both `allocations` here AND already folded into "already
    consumed" by the time that call runs).
    """

    total_revenue = Decimal("0")
    total_cost = Decimal("0")

    for allocation in allocations:
        product = next(
            product
            for product in products
            if product.id == allocation["product_id"]
        )

        quantity = Decimal(
            str(allocation["quantity"])
        )

        total_revenue += (
            product.selling_price * quantity
        )

        unit_profit = calculate_unit_profit(
            product,
            requirements,
            cycle_resources,
        )

        total_cost += (
            product.selling_price - unit_profit
        ) * quantity

    total_profit = total_revenue - total_cost

    resource_usage = calculate_optimized_resource_usage(
        allocations,
        cycle_resources,
        requirements,
        already_consumed_by_resource_id,
    )

    bottlenecks = identify_optimization_bottlenecks(
        resource_usage
    )

    return {
        "cycle_id": cycle_id,
        "status": status.upper(),
        "objective": "MAX_PROFIT",
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "allocations": allocations,
        "resource_usage": resource_usage,
        "bottlenecks": bottlenecks,
    }

def calculate_optimized_resource_usage(
    allocations: list[dict],
    cycle_resources,
    requirements,
    already_consumed_by_resource_id: dict[int, Decimal] | None = None,
) -> list[dict]:
    """
    Calculate resource usage based on the optimized
    production quantities.

    A CycleResource row whose resource_id is no longer referenced by
    any current ProductResourceRequirement (e.g. a resource that was
    superseded/renamed and had its requirements remapped onto a
    canonical row elsewhere - see migration 7f3cba51324d - or any
    other stray/orphaned CycleResource row) is skipped entirely here,
    rather than reported as a fabricated "Unknown"/"" entry with
    required_quantity 0. This is display-only: such a row already
    contributes a mathematically trivial `0 <= available_quantity`
    constraint in add_resource_constraints() regardless (empty
    resource_requirements -> zero consumption), so it never affected
    the ILP's chosen quantities, cost, or profit - only this reporting
    step is changed. Nothing is deleted or written back to the
    database; the CycleResource row itself is untouched.

    `already_consumed_by_resource_id`, when given, is what earlier
    applications in this same cycle have already consumed - the
    returned `consumed_quantity` is that figure, `required_quantity`
    stays exactly what it always meant (what THIS allocation alone
    would require), and `remaining_quantity` becomes CUMULATIVE:
    available_quantity - consumed_quantity - required_quantity. This
    is deliberately NOT floored at zero, unlike the solver's own
    constraint bound (_remaining_cycle_capacity) - it must be able to
    go negative so identify_optimization_bottlenecks' existing
    shortage detection (which reads a negative remaining_quantity as a
    shortage) keeps working unchanged, and so the preview can warn
    about a resource that even a freshly-solved plan would exceed once
    prior consumption is counted (e.g. available_quantity was edited
    downward after this plan was solved). None (the default)
    reproduces the original behavior exactly: consumed_quantity 0,
    remaining_quantity computed from `allocations` alone.
    """

    allocation_quantities = {
        allocation["product_id"]: allocation["quantity"]
        for allocation in allocations
    }

    resource_names = {
        resource.id: resource.name
        for _, resource in requirements
    }

    resource_units = {
        resource.id: resource.unit
        for _, resource in requirements
    }

    usage = []

    for cycle_resource in cycle_resources:
        resource_id = cycle_resource.resource_id

        if resource_id not in resource_names:
            continue

        required_quantity = Decimal("0")

        for requirement, resource in requirements:
            if requirement.resource_id != resource_id:
                continue

            product_quantity = allocation_quantities.get(
                requirement.product_id,
                0,
            )

            required_quantity += (
                requirement.quantity_required
                * Decimal(str(product_quantity))
            )

        # Matches add_resource_constraints' zero-capacity treatment of
        # an inactive resource - reporting its stale available_quantity
        # here would make it look like there was slack the solver
        # never actually had access to.
        available_quantity = (
            cycle_resource.available_quantity
            if cycle_resource.resource.is_active
            else Decimal("0")
        )

        consumed_quantity = (
            already_consumed_by_resource_id or {}
        ).get(resource_id, Decimal("0"))

        remaining_quantity = (
            available_quantity
            - consumed_quantity
            - required_quantity
        )

        usage.append(
            {
                "resource_id": resource_id,
                "resource_name": resource_names[resource_id],
                "unit": resource_units.get(
                    resource_id,
                    "",
                ),
                "required_quantity": required_quantity,
                "available_quantity": available_quantity,
                "consumed_quantity": consumed_quantity,
                "remaining_quantity": remaining_quantity,
            }
        )

    return usage

def identify_optimization_bottlenecks(
    resource_usage: list[dict],
) -> list[dict]:
    """
    Identify resources that are binding or have a shortage.
    """

    bottlenecks = []

    for resource in resource_usage:
        remaining_quantity = resource["remaining_quantity"]

        if remaining_quantity <= BOTTLENECK_REMAINING_THRESHOLD:
            bottlenecks.append(
                {
                    "resource_id": resource["resource_id"],
                    "resource_name": resource["resource_name"],
                    "unit": resource["unit"],
                    "remaining_quantity": remaining_quantity,
                    "is_binding": remaining_quantity == Decimal("0"),
                    "shortage_quantity": (
                        abs(remaining_quantity)
                        if remaining_quantity < Decimal("0")
                        else Decimal("0")
                    ),
                }
            )

    return bottlenecks

def apply_optimization(
    db: Session,
    cycle_id: int,
) -> dict:
    data = get_optimization_data(
        db,
        cycle_id,
    )

    if not data["cycle_resources"]:
        raise ValueError(
            "Production cycle has no resources configured"
        )

    # Serialises concurrent applies for this cycle. Without it, two
    # parallel clicks could interleave their ProductionAllocation
    # delete+insert and ledger append, corrupting the "one row per
    # product, latest apply wins" invariant. The
    # uq_production_application_run constraint catches a double
    # application of the SAME run regardless, but two DIFFERENT runs
    # applied simultaneously would slip past it, so the lock is what
    # keeps each apply's read-check-write atomic relative to the
    # next. Held until this function's commit/rollback.
    locked_cycle = db.execute(
        select(ProductionCycle)
        .where(ProductionCycle.id == cycle_id)
        .with_for_update()
    ).scalar_one_or_none()

    if locked_cycle is None:
        raise ValueError("Production cycle not found")

    # Read once, right after the lock, and reused below to explain an
    # all-zero plan (which resource has nothing left, if any) - no
    # longer used to validate the proposed allocation against
    # remaining capacity (see the business-rule comment further
    # down), only for that explanatory message.
    already_consumed = get_cycle_consumed_by_resource(db, cycle_id)

    optimization_run = (
        get_latest_optimization_history_run(
            db,
            cycle_id,
        )
    )

    if optimization_run is None:
        raise ValueError(
            "No optimization result found for production cycle."
        )

    if optimization_run.status != "OPTIMAL":
        raise ValueError(
            "Only an optimal optimization result can be applied."
        )

    # Both guards run BEFORE the ProductionAllocation delete further
    # down: a summary-only imported record (or any run that somehow has
    # no per-product rows) would otherwise clear every current
    # allocation, insert none, and commit a zero-utilization snapshot
    # as if it were a real applied plan.
    if optimization_run.is_summary_only:
        raise ValueError(
            "This optimization record is summary-only and cannot be "
            "applied. Generate a new production plan instead."
        )

    if not optimization_run.results:
        raise ValueError(
            "This optimization record has no product-level results and "
            "cannot be applied. Generate a new production plan instead."
        )

    # Duplicate-application guard. Checked here, before anything is
    # written, so the caller gets an explanatory 400 instead of the
    # uq_production_application_run IntegrityError - and so a
    # double-clicked Apply cannot add the same units to available
    # stock twice. Deliberately phrased as "generate a new plan":
    # re-applying is never the right remedy, producing more is.
    if has_application_for_run(db, optimization_run.id):
        raise ValueError(
            "This production plan has already been applied "
            "and cannot be applied again. Generate a new production "
            "plan to produce more."
        )

    allocations = []

    for result in optimization_run.results:
        product = next(
            (
                product
                for product in data["products"]
                if product.id == result.product_id
            ),
            None,
        )

        if product is None:
            continue

        quantity = int(result.recommended_quantity)
        minimum_demand = product.minimum_demand or Decimal("0")

        allocations.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_profit": result.unit_profit,
                "total_profit": result.total_profit,
                "minimum_demand": minimum_demand,
                "shortfall": max(
                    Decimal("0"),
                    minimum_demand - Decimal(str(quantity)),
                ),
            }
        )

    if not any(
        allocation["quantity"] > 0
        for allocation in allocations
    ):
        exhausted = _exhausted_resources(
            data["cycle_resources"],
            already_consumed,
        )

        if exhausted:
            resource_list = ", ".join(
                f"{resource['resource_name']} "
                f"(0 {resource['unit']} remaining)"
                for resource in exhausted
            )

            raise ValueError(
                "This optimization record has no applicable "
                "product-level results because no capacity remains "
                f"for {resource_list}. This is a resource shortage, "
                "not a minimum-demand conflict - add capacity to one "
                "of these resources, or wait for a future cycle, "
                "before generating a new production plan."
            )

        raise ValueError(
            "This optimization record has no applicable product-level "
            "results. Generate a new production plan instead."
        )

    proposed_quantities = {
        allocation["product_id"]: Decimal(str(allocation["quantity"]))
        for allocation in allocations
    }

    # Business-rule change (approved): Apply no longer rejects a plan
    # for exceeding what's left of a resource's declared capacity
    # after earlier applications this cycle - students explicitly
    # want Generate -> Apply -> Generate -> Apply... repeatable in the
    # same cycle, with no resource replenishment or new cycle required
    # in between. A remaining-capacity shortage check used to run here
    # (find_resource_capacity_shortages with already_consumed) and
    # raise before any write; it has been removed outright, not
    # loosened - nothing computes or inspects a shortage for this
    # purpose anymore. Resource consumption is still recorded exactly
    # as consumed below (never capped, never reset), and utilization
    # reporting still shows the true, uncapped total - including well
    # over 100% - via calculate_optimized_resource_usage /
    # _remaining_cycle_capacity, which were already never floored for
    # exactly this reason. Every OTHER guard above (summary-only run,
    # no product-level results, duplicate application for this run)
    # is untouched.

    # What this application will consume, recorded on the ledger so
    # the NEXT application in this cycle is offset by it - the exact
    # quantities this plan requires, regardless of whether the cycle
    # actually has that much declared capacity left (no longer
    # validated against remaining capacity - see the comment above).
    consumption = calculate_resource_requirements_for_quantities(
        db,
        proposed_quantities,
    )

    consumed_resources = [
        {
            "resource_id": item["resource_id"],
            "resource_name": item["resource_name"],
            "unit": item["unit"],
            "consumed_quantity": item["required_quantity"],
        }
        for item in consumption
    ]

    db.query(ProductionAllocation).filter(
        ProductionAllocation.production_cycle_id == cycle_id
    ).delete(
        synchronize_session=False
    )

    applied_at = datetime.utcnow()

    for allocation in allocations:
        quantity = allocation["quantity"]

        if quantity <= 0:
            continue

        db.add(
            ProductionAllocation(
                production_cycle_id=cycle_id,
                product_id=allocation["product_id"],
                quantity=quantity,
                applied_at=applied_at,
            )
        )

    try:
        # Flushed (not committed) so calculate_resource_utilization()
        # below - which reads ProductionAllocation back via a SELECT
        # - sees the rows just added above in this same session.
        # autoflush is disabled project-wide (see
        # app/database/connection.py), so without this the query
        # would still see the pre-apply allocations.
        db.flush()

        # Append-only production history. Written in the SAME
        # transaction as the ProductionAllocation rows and the
        # utilization snapshot below, so the current plan, the
        # production history, and the utilization snapshot can never
        # disagree about whether this apply happened.
        save_production_application(
            db,
            cycle_id,
            optimization_run.id,
            {
                allocation["product_id"]: Decimal(
                    str(allocation["quantity"])
                )
                for allocation in allocations
            },
            consumed_resources,
        )

        # Resource Utilization History is a snapshot of applied
        # production, never of the optimizer's preview - this is the
        # ONLY place it's created (generating a plan does not reach
        # here). Passed the cycle's CUMULATIVE ledger consumption
        # rather than letting it re-derive consumption from
        # ProductionAllocation: the allocation holds only the latest
        # plan, so without this the snapshot taken after a second
        # application would report only that application's share and
        # show capacity the cycle has already spent. Persisted in the
        # SAME transaction (save_resource_utilization_history does
        # not commit) so everything here succeeds or rolls back
        # together atomically.
        #
        # Deliberately a SECOND call to
        # get_cycle_consumed_by_resource: the one above (already_
        # consumed) excludes this apply - it's only used for the
        # all-zero-plan explanation earlier; this one is the figure
        # the snapshot should SHOW (includes this apply too, via the
        # flush inside save_production_application). Do not collapse
        # them.
        cumulative_consumed = get_cycle_consumed_by_resource(
            db,
            cycle_id,
        )

        utilization = calculate_resource_utilization(
            db,
            cycle_id,
            consumption_override=cumulative_consumed,
        )

        save_resource_utilization_history(
            db,
            cycle_id,
            utilization,
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return build_optimization_result(
        cycle_id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        allocations,
        optimization_run.status,
    )

def add_forecast_constraints(
    problem: pulp.LpProblem,
    variables: dict[int, pulp.LpVariable],
    forecast: dict[int, Decimal],
) -> None:
    """
    Limit production quantities to forecast demand.
    """

    for product_id, forecast_quantity in forecast.items():
        variable = variables.get(product_id)

        if variable is None:
            continue

        problem += (
            variable <= float(forecast_quantity),
            f"forecast_{product_id}_limit",
        )