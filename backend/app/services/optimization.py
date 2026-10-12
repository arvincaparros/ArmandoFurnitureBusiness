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
    Resource,
    OptimizationResult,
    OptimizationRun,
)
from app.services.optimization_history import (
    get_latest_optimization_history_run,
)
from app.services.production_calculation import (
    BOTTLENECK_REMAINING_THRESHOLD,
    find_resource_capacity_shortages,
    format_capacity_shortage_message,
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

    cycle_resources_statement = select(
        CycleResource
    ).where(
        CycleResource.production_cycle_id == cycle_id
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
) -> None:
    """
    Pre-solve check: confirms the exact minimum-demand vector alone
    (every product held at its own minimum, everything else at 0)
    fits inside this cycle's resource capacities. That single point is
    a valid feasibility witness for "can every minimum be satisfied
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

        available = (
            cycle_resource.available_quantity
            if cycle_resource.resource.is_active
            else Decimal("0")
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

def add_resource_constraints(
    problem: pulp.LpProblem,
    variables: dict[int, pulp.LpVariable],
    cycle_resources,
    requirements,
) -> None:
    """
    Add one resource constraint for each resource available
    in the production cycle.

    Total resource consumption must not exceed
    the available quantity.
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
        available_quantity = (
            cycle_resource.available_quantity
            if cycle_resource.resource.is_active
            else Decimal("0")
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
) -> None:
    """
    Set the optimization objective to maximize
    total production profit.
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

def _is_minimum_demand_vector_feasible(
    products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
) -> bool:
    """
    Phase 1/2 branch decision for solve_optimization. Reuses
    validate_minimum_demand_capacity/validate_minimum_demand_forecast
    completely unchanged as a non-raising feasibility witness: if
    either would raise (the exact minimum-demand vector doesn't fit
    this cycle's resource capacities, or conflicts with a forecast
    ceiling), the full vector cannot be satisfied simultaneously, and
    Phase 2 (adaptive) takes over. Deliberately does not call
    validate_minimum_demand_resource_availability - that check is a
    data-completeness gate (a resource with no CycleResource row at
    all this cycle), not a capacity/forecast feasibility question, and
    already runs unconditionally from the router before
    solve_optimization is ever called.
    """

    try:
        validate_minimum_demand_capacity(
            products,
            cycle_resources,
            requirements,
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
    problem.solve(
        pulp.PULP_CBC_CMD(msg=False)
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

    problem += pulp.lpSum(
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

    _solve_stage_or_raise(
        problem, "Stage 3 (profitability coverage tie-break)"
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

    add_profit_objective(
        problem,
        variables,
        products,
        requirements,
        cycle_resources,
    )

    _solve_stage_or_raise(problem, "Stage 5 (final profit maximization)")

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
        "objective_value": problem.objective.value(),
    }


def _solve_with_adaptive_minimum_demand(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
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
    )

    p2_star = _solve_stage2_total_coverage(
        cycle_id,
        products,
        positive_products,
        p1_star,
        cycle_resources,
        requirements,
        forecast,
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
    )

    z_star = _solve_stage4_proportional_fairness(
        cycle_id,
        products,
        covered_ids,
        positive_products,
        cycle_resources,
        requirements,
        forecast,
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
    )


def _solve_with_hard_minimum_demand(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    forecast: dict[int, Decimal] | None,
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
    )

    if forecast is not None:
        add_forecast_constraints(
            problem,
            variables,
            forecast,
        )

    add_profit_objective(
        problem,
        variables,
        products,
        requirements,
        cycle_resources,
    )

    problem.solve(
        pulp.PULP_CBC_CMD(msg=False)
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
        "objective_value": problem.objective.value(),
    }


def solve_optimization(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    objective="MAX_PROFIT",
    forecast: dict[int, Decimal] | None = None,
) -> dict:
    """
    Build and solve the integer linear programming model.

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
    ):
        try:
            return _solve_with_hard_minimum_demand(
                cycle_id,
                products,
                cycle_resources,
                requirements,
                forecast,
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
    )

def build_optimization_result(
    cycle_id: int,
    products,
    cycle_resources,
    requirements,
    allocations: list[dict],
    status: str,
) -> dict:
    """
    Build the complete optimization result.
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

        remaining_quantity = (
            available_quantity - required_quantity
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

    # Revalidate the ENTIRE proposed allocation against current
    # resource state before touching the database at all - the saved
    # OptimizationResult rows reflect whatever CycleResource/
    # ProductResourceRequirement looked like the last time /optimize
    # ran, which may no longer be true by the time Apply is clicked
    # (a resource's capacity or active state changed, or a product's
    # requirements changed, in between). find_resource_capacity_
    # shortages treats an inactive resource as zero capacity here too,
    # matching add_resource_constraints. Checked before the delete
    # below runs, so a stale/now-infeasible plan is rejected atomically
    # - nothing about the existing allocation is touched.
    proposed_quantities = {
        allocation["product_id"]: Decimal(str(allocation["quantity"]))
        for allocation in allocations
    }

    shortages = find_resource_capacity_shortages(
        db,
        cycle_id,
        proposed_quantities,
    )

    if shortages:
        raise ValueError(
            format_capacity_shortage_message(
                shortages,
                "Cannot apply this production plan - resources or "
                "requirements have changed since it was generated and "
                "it is no longer feasible. Please regenerate the "
                "Production Plan",
            )
        )

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

        # Resource Utilization History is a snapshot of applied
        # production, never of the optimizer's preview - this is the
        # ONLY place it's created (generating a plan does not reach
        # here). Computed from the allocations just flushed above,
        # then persisted in the SAME transaction as those allocations
        # (save_resource_utilization_history does not commit) so both
        # succeed or both roll back together atomically.
        utilization = calculate_resource_utilization(db, cycle_id)

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

def get_latest_optimization_history_run(
    db: Session,
    cycle_id: int,
) -> OptimizationRun | None:
    statement = (
        select(OptimizationRun)
        .where(
            OptimizationRun.production_cycle_id
            == cycle_id
        )
        .order_by(
            OptimizationRun.started_at.desc(),
            OptimizationRun.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)

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