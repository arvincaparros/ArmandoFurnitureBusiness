from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.allocation import (
    ProductionAllocationCreate,
    ProductionAllocationFinancialsResponse,
    ProductionAllocationResponse,
    ProductionAllocationUpdate,
)
from app.services.allocation import (
    create_allocation,
    delete_allocation,
    get_allocation,
    get_allocations_with_financials,
    update_allocation,
)
from app.services.auth import get_current_user

router = APIRouter(
    prefix="/api/production-cycles/{cycle_id}/allocations",
    tags=["Production Allocations"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[ProductionAllocationFinancialsResponse],
)
def list_allocations(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    return get_allocations_with_financials(db, cycle_id)


@router.post(
    "",
    response_model=ProductionAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_allocation(
    cycle_id: int,
    data: ProductionAllocationCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_allocation(
            db,
            cycle_id,
            data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{product_id}",
    response_model=ProductionAllocationResponse,
)
def update_existing_allocation(
    cycle_id: int,
    product_id: int,
    data: ProductionAllocationUpdate,
    db: Session = Depends(get_db),
):
    allocation = get_allocation(
        db,
        cycle_id,
        product_id,
    )

    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production allocation not found",
        )

    return update_allocation(
        db,
        allocation,
        data,
    )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_existing_allocation(
    cycle_id: int,
    product_id: int,
    db: Session = Depends(get_db),
):
    allocation = get_allocation(
        db,
        cycle_id,
        product_id,
    )

    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production allocation not found",
        )

    delete_allocation(
        db,
        allocation,
    )