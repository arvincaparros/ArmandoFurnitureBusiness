from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CycleResource,
    Product,
    ProductionAllocation,
    ProductionCycle,
    ProductResourceRequirement,
    Resource,
)
from app.schemas.allocation import (
    ProductionAllocationCreate,
    ProductionAllocationUpdate,
)
from app.services.production_calculation import (
    find_resource_capacity_shortages,
    format_capacity_shortage_message,
)


def _validate_proposed_allocation_capacity(
    db: Session,
    cycle_id: int,
    product_id: int,
    proposed_quantity,
) -> None:
    """
    Checks a proposed create/update against every resource shared with
    every OTHER allocation already in this cycle - the proposed
    quantity REPLACES this product's own current allocation (if any)
    in the projected total, so a no-op update or a reduction is never
    double-counted against itself.
    """

    quantities_by_product_id = {
        allocation.product_id: allocation.quantity
        for allocation in get_allocations(db, cycle_id)
    }

    quantities_by_product_id[product_id] = proposed_quantity

    shortages = find_resource_capacity_shortages(
        db,
        cycle_id,
        quantities_by_product_id,
    )

    if shortages:
        raise ValueError(
            format_capacity_shortage_message(
                shortages,
                "Cannot save this allocation - it would exceed "
                "available resource capacity",
            )
        )


def get_allocations(
    db: Session,
    cycle_id: int,
) -> list[ProductionAllocation]:
    statement = (
        select(ProductionAllocation)
        .where(
            ProductionAllocation.production_cycle_id == cycle_id
        )
        .order_by(ProductionAllocation.id)
    )

    return list(
        db.scalars(statement).all()
    )


def get_allocations_with_financials(
    db: Session,
    cycle_id: int,
) -> list[dict]:
    """
    Read-only financial breakdown for this cycle's COMMITTED
    ProductionAllocation rows (Revision #2) - priced with CURRENT
    Product/Resource/CycleResource data, since ProductionAllocation
    itself stores no apply-time price snapshot (see the Revision #2
    investigation report: no snapshot architecture exists, and this
    revision deliberately doesn't add one).

    Deliberately a separate calculation from
    optimization.py::calculate_unit_profit, not a call to it: that
    function silently treats a resource with no current price as zero
    cost (a known, pre-existing gap - see the comment on it - left
    unfixed here because fixing it would change
    add_profit_objective()'s objective function, which this revision
    must not touch). Here, instead, a product's cost/profit is
    reported as unavailable (None) whenever any non-labor requirement
    can't be fully and reliably priced right now - either the
    resource is inactive (Revision #1 soft-delete) or this cycle has
    no CycleResource price for it - matching Revision #1's "never
    silently understate" rule for the allocation read/display path.
    Total revenue never depends on resource pricing, so it's always
    computable from Product.selling_price alone.

    Never touches the optimizer/solver - this only reads already-
    committed ProductionAllocation.quantity values.
    """

    allocations = get_allocations(db, cycle_id)

    if not allocations:
        return []

    product_ids = list(
        {allocation.product_id for allocation in allocations}
    )

    products_by_id = {
        product.id: product
        for product in db.scalars(
            select(Product).where(Product.id.in_(product_ids))
        ).all()
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

    requirements_by_product: dict[
        int, list[tuple[ProductResourceRequirement, Resource]]
    ] = {}

    for requirement, resource in requirement_rows:
        requirements_by_product.setdefault(
            requirement.product_id, []
        ).append((requirement, resource))

    cycle_resources = db.scalars(
        select(CycleResource).where(
            CycleResource.production_cycle_id == cycle_id
        )
    ).all()

    price_by_resource_id = {
        cycle_resource.resource_id: cycle_resource.unit_price
        for cycle_resource in cycle_resources
    }

    results = []

    for allocation in allocations:
        product = products_by_id.get(allocation.product_id)
        quantity = allocation.quantity

        base_row = {
            "id": allocation.id,
            "production_cycle_id": allocation.production_cycle_id,
            "product_id": allocation.product_id,
            "quantity": quantity,
        }

        # quantity <= 0 can't currently reach a committed allocation
        # (create_allocation requires gt=0, apply_optimization skips
        # non-positive quantities) - guarded anyway so a zero-impact
        # row is unambiguously all-zero rather than depending on
        # whether its resources happen to be priced.
        if product is None or quantity <= 0:
            results.append(
                {
                    **base_row,
                    "total_revenue": Decimal("0"),
                    "total_cost": Decimal("0"),
                    "total_profit": Decimal("0"),
                }
            )
            continue

        total_revenue = product.selling_price * quantity

        is_fully_priced = True
        total_resource_cost = Decimal("0")

        for requirement, resource in requirements_by_product.get(
            product.id, []
        ):
            if resource.resource_type.strip().lower() == "labor":
                continue

            if not resource.is_active:
                is_fully_priced = False
                break

            unit_price = price_by_resource_id.get(resource.id)

            if unit_price is None:
                is_fully_priced = False
                break

            total_resource_cost += (
                requirement.quantity_required * unit_price
            )

        if is_fully_priced:
            total_cost = (
                total_resource_cost + product.labor_cost
            ) * quantity
            total_profit = total_revenue - total_cost
        else:
            total_cost = None
            total_profit = None

        results.append(
            {
                **base_row,
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "total_profit": total_profit,
            }
        )

    return results


def get_allocation(
    db: Session,
    cycle_id: int,
    product_id: int,
) -> ProductionAllocation | None:
    statement = select(ProductionAllocation).where(
        ProductionAllocation.production_cycle_id == cycle_id,
        ProductionAllocation.product_id == product_id,
    )

    return db.scalars(statement).first()


def create_allocation(
    db: Session,
    cycle_id: int,
    data: ProductionAllocationCreate,
) -> ProductionAllocation:
    cycle = db.get(
        ProductionCycle,
        cycle_id,
    )

    if cycle is None:
        raise ValueError(
            "Production cycle not found"
        )

    product = db.get(
        Product,
        data.product_id,
    )

    if product is None:
        raise ValueError(
            "Product not found"
        )

    existing = get_allocation(
        db,
        cycle_id,
        data.product_id,
    )

    if existing is not None:
        raise ValueError(
            "Product already has an allocation in this production cycle"
        )

    _validate_proposed_allocation_capacity(
        db,
        cycle_id,
        data.product_id,
        data.quantity,
    )

    allocation = ProductionAllocation(
        production_cycle_id=cycle_id,
        product_id=data.product_id,
        quantity=data.quantity,
    )

    try:
        db.add(allocation)
        db.commit()
        db.refresh(allocation)

        return allocation

    except Exception:
        db.rollback()
        raise


def update_allocation(
    db: Session,
    allocation: ProductionAllocation,
    data: ProductionAllocationUpdate,
) -> ProductionAllocation:
    _validate_proposed_allocation_capacity(
        db,
        allocation.production_cycle_id,
        allocation.product_id,
        data.quantity,
    )

    allocation.quantity = data.quantity

    try:
        db.commit()
        db.refresh(allocation)

        return allocation

    except Exception:
        db.rollback()
        raise


def delete_allocation(
    db: Session,
    allocation: ProductionAllocation,
) -> None:
    try:
        db.delete(allocation)
        db.commit()

    except Exception:
        db.rollback()
        raise