from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.product import (
    ProductResourceRequirementCreate,
    ProductResourceRequirementResponse,
    ProductResourceRequirementUpdate,
)
from app.services.auth import get_current_user
from app.services.product_resource_requirement import (
    create_product_resource_requirement,
    delete_product_resource_requirement,
    get_product_resource_requirement,
    get_product_resource_requirements,
    update_product_resource_requirement,
)


router = APIRouter(
    prefix="/api/products/{product_id}/resources",
    tags=["Product Resources"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[ProductResourceRequirementResponse],
    summary="List product resource requirements",
)
def list_product_resources(
    product_id: int,
    db: Session = Depends(get_db),
):
    return get_product_resource_requirements(
        db,
        product_id,
    )


@router.post(
    "",
    response_model=ProductResourceRequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a resource requirement to a product",
)
def create_product_resource(
    product_id: int,
    data: ProductResourceRequirementCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_product_resource_requirement(
            db,
            product_id,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{resource_id}",
    response_model=ProductResourceRequirementResponse,
    summary="Update product resource requirement",
)
def update_product_resource(
    product_id: int,
    resource_id: int,
    data: ProductResourceRequirementUpdate,
    db: Session = Depends(get_db),
):
    requirement = get_product_resource_requirement(
        db,
        product_id,
        resource_id,
    )

    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product resource requirement not found",
        )

    return update_product_resource_requirement(
        db,
        requirement,
        data,
    )


@router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove product resource requirement",
)
def delete_product_resource(
    product_id: int,
    resource_id: int,
    db: Session = Depends(get_db),
):
    requirement = get_product_resource_requirement(
        db,
        product_id,
        resource_id,
    )

    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product resource requirement not found",
        )

    delete_product_resource_requirement(
        db,
        requirement,
    )