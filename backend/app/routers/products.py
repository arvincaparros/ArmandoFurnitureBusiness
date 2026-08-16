from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.auth import get_current_user
from app.services.product import (
    create_product,
    delete_product,
    get_product,
    get_products,
    update_product,
)


router = APIRouter(
    prefix="/api/products",
    tags=["Products"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[ProductResponse],
)
def list_products(
    include_inactive: bool = Query(
        default=False,
        description="Include inactive products in the results",
    ),
    db: Session = Depends(get_db),
):
    return get_products(db, include_inactive)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
)
def get_product_by_id(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = get_product(
        db,
        product_id,
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
):
    return create_product(
        db,
        product_data,
    )


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
)
def update_existing_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
):
    product = get_product(
        db,
        product_id,
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return update_product(
        db,
        product,
        product_data,
    )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_existing_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = get_product(
        db,
        product_id,
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    delete_product(
        db,
        product,
    )