from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.transaction import (
    SalesTransactionCreate,
    SalesTransactionResponse,
    SalesTransactionUpdate,
)
from app.services.transaction import (
    create_transaction,
    delete_transaction,
    get_transaction,
    get_transactions,
    update_transaction,
)


router = APIRouter(
    prefix="/api/transactions",
    tags=["Sales Transactions"],
)


@router.get(
    "",
    response_model=list[SalesTransactionResponse],
)
def list_transactions(
    db: Session = Depends(get_db),
):
    return get_transactions(db)


@router.get(
    "/{transaction_id}",
    response_model=SalesTransactionResponse,
)
def get_transaction_by_id(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    transaction = get_transaction(
        db,
        transaction_id,
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales transaction not found",
        )

    return transaction


@router.post(
    "",
    response_model=SalesTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_transaction(
    data: SalesTransactionCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_transaction(
            db,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{transaction_id}",
    response_model=SalesTransactionResponse,
)
def update_existing_transaction(
    transaction_id: int,
    data: SalesTransactionUpdate,
    db: Session = Depends(get_db),
):
    transaction = get_transaction(
        db,
        transaction_id,
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales transaction not found",
        )

    return update_transaction(
        db,
        transaction,
        data,
    )


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_existing_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    transaction = get_transaction(
        db,
        transaction_id,
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales transaction not found",
        )

    delete_transaction(
        db,
        transaction,
    )