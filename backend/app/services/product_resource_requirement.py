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