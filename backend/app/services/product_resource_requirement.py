from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Product,
    ProductResourceRequirement,
    Resource,
)
from app.schemas.product import (
    ProductResourceRequirementCreate,
    ProductResourceRequirementUpdate,
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
    """
    Business-rule change (approved): a product's resource
    requirements (its BOM) can be edited, removed, or replaced
    freely, regardless of any currently applied ProductionAllocation
    or that allocation's resource capacity. A capacity-shortage check
    against applied allocations used to run here
    (find_resource_capacity_shortages via
    _validate_requirement_change_against_applied_allocations,
    removed outright); editing a product's requirements must never be
    blocked by, nor require resetting, past production. Historical
    ProductionApplication/ProductionApplicationResourceItem rows and
    resource utilization history are untouched by this change - they
    are immutable snapshots of what was actually produced and
    consumed, never recomputed from the live requirement. A future
    Generate run reads ProductResourceRequirement fresh each time (see
    production_calculation.py), so it automatically uses whatever is
    saved here next.
    """

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