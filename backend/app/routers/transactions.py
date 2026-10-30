from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.transaction import (
    SalesTransactionCreate,
    SalesTransactionListResponse,
    SalesTransactionResponse,
    SalesTransactionUpdate,
)
from app.services.auth import get_current_user
from app.services.transaction import (
    create_transaction,
    delete_transaction,
    get_transaction,
    get_transaction_list,
    update_transaction,
)


router = APIRouter(
    prefix="/api/transactions",
    tags=["Sales Transactions"],
    dependencies=[Depends(get_current_user)],
)


# Three mutually exclusive modes, all on this one endpoint:
#
#   (no params)              -> the 7 most recent DISTINCT transaction
#                               dates present in the table, anchored to
#                               the newest row rather than to today
#   start_date / end_date    -> that custom range, inclusive both ends;
#                               either bound may be sent alone
#   show_all=true            -> the complete history, no window
#
# Sending no parameters deliberately does NOT mean "everything" - a
# caller that wants the full table must ask for it explicitly with
# show_all=true, so the intent is visible at the call site. The
# response is an object, not a bare array: the client cannot label or
# empty-state a window the server chose for it, so the resolved window
# travels with the rows.
@router.get(
    "",
    response_model=SalesTransactionListResponse,
)
def list_transactions(
    start_date: date | None = Query(
        default=None,
        description=(
            "Inclusive start of a custom range (YYYY-MM-DD). May be "
            "sent without end_date for an open-ended window."
        ),
    ),
    end_date: date | None = Query(
        default=None,
        description=(
            "Inclusive end of a custom range (YYYY-MM-DD). Must not be "
            "earlier than start_date."
        ),
    ),
    show_all: bool = Query(
        default=False,
        description=(
            "Return the complete transaction history instead of the "
            "default latest-available window. Cannot be combined with "
            "start_date or end_date."
        ),
    ),
    db: Session = Depends(get_db),
):
    try:
        return get_transaction_list(
            db,
            start_date=start_date,
            end_date=end_date,
            show_all=show_all,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


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