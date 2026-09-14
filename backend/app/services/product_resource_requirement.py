from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Product,
    ProductionAllocation,
    ProductResourceRequirement,
    Resource,
)
from app.schemas.product import (
    ProductResourceRequirementCreate,
    ProductResourceRequirementUpdate,
)
from app.services.production_calculation import (
    find_resource_capacity_shortages,
    format_capacity_shortage_message,
)


def _validate_requirement_change_against_applied_allocations(
    db: Session,
    product_id: int,
    resource_id: int,
    new_quantity_required,
) -> None:
    """
    A ProductResourceRequirement isn't scoped to one production cycle
    - it's the product's own BOM, shared by every cycle that currently
    has an applied ProductionAllocation for it. Checks every such
    cycle: with this one requirement hypothetically at the proposed
    new quantity_required (everything else - including this product's
    own already-applied quantity - unchanged), would that cycle's
    resource capacity still hold? Rejects if not, for any cycle.
    """

    affected_cycle_ids = {
        allocation.production_cycle_id
        for allocation in db.scalars(
            select(ProductionAllocation).where(
                ProductionAllocation.product_id == product_id
            )
        ).all()
    }

    for cycle_id in affected_cycle_ids:
        quantities_by_product_id = {
            allocation.product_id: allocation.quantity
            for allocation in db.scalars(
                select(ProductionAllocation).where(
                    ProductionAllocation.production_cycle_id == cycle_id
                )
            ).all()
        }

        shortages = find_resource_capacity_shortages(
            db,
            cycle_id,
            quantities_by_product_id,
            requirement_override=(
                product_id,
                resource_id,
                new_quantity_required,
            ),
        )

        if shortages:
            raise ValueError(
                format_capacity_shortage_message(
                    shortages,
                    "Cannot update this resource requirement - it "
                    "would make the currently applied production "
                    f"allocation for production cycle {cycle_id} "
                    "exceed available capacity",
                )
            )


def get_product_resource_requirements(
    db: Session,
    product_id: int,
) -> list[ProductResourceRequirement]:
    statement = (
        select(ProductResourceRequirement)
        .where(
            ProductResourceRequirement.product_id == product_id
        )
        .order_by(ProductResourceRequirement.id)
    )

    return list(
        db.scalars(statement).all()
    )


def get_product_resource_requirement(
    db: Session,
    product_id: int,
    resource_id: int,
) -> ProductResourceRequirement | None:
    statement = select(
        ProductResourceRequirement
    ).where(
        ProductResourceRequirement.product_id == product_id,
        ProductResourceRequirement.resource_id == resource_id,
    )

    return db.scalars(statement).first()


def create_product_resource_requirement(
    db: Session,
    product_id: int,
    data: ProductResourceRequirementCreate,
) -> ProductResourceRequirement:
    product = db.get(Product, product_id)

    if product is None:
        raise ValueError("Product not found")

    resource = db.get(Resource, data.resource_id)

    if resource is None:
        raise ValueError("Resource not found")

    existing = get_product_resource_requirement(
        db,
        product_id,
        data.resource_id,
    )

    if existing is not None:
        raise ValueError(
            "Resource requirement already exists for this product"
        )

    requirement = ProductResourceRequirement(
        product_id=product_id,
        resource_id=data.resource_id,
        quantity_required=data.quantity_required,
    )

    try:
        db.add(requirement)
        db.commit()
        db.refresh(requirement)

        return requirement

    except Exception:
        db.rollback()
        raise


def update_product_resource_requirement(
    db: Session,
    requirement: ProductResourceRequirement,
    data: ProductResourceRequirementUpdate,
) -> ProductResourceRequirement:
    _validate_requirement_change_against_applied_allocations(
        db,
        requirement.product_id,
        requirement.resource_id,
        data.quantity_required,
    )

    requirement.quantity_required = (
        data.quantity_required
    )

    try:
        db.commit()
        db.refresh(requirement)

        return requirement

    except Exception:
        db.rollback()
        raise


def delete_product_resource_requirement(
    db: Session,
    requirement: ProductResourceRequirement,
) -> None:
    try:
        db.delete(requirement)
        db.commit()

    except Exception:
        db.rollback()
        raise