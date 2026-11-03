from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import OpeningInventorySet, User
from app.schemas.opening_inventory import (
    OpeningInventorySetCreate,
    OpeningInventorySetResponse,
    OpeningInventorySetUpdate,
    OpeningInventoryStatusResponse,
)
from app.services.auth import get_current_user
from app.services.opening_inventory import (
    create_opening_inventory_set,
    get_draft_opening_inventory_set,
    get_opening_inventory_set,
    get_opening_inventory_sets,
    get_reviewed_opening_inventory_set,
    is_stock_validation_enabled,
    review_opening_inventory_set,
    update_opening_inventory_set,
)


router = APIRouter(
    prefix="/api/opening-inventory",
    tags=["Opening Inventory"],
    dependencies=[Depends(get_current_user)],
)


def _to_response(
    inventory_set: OpeningInventorySet,
) -> OpeningInventorySetResponse:
    """
    Pydantic v2's from_attributes validation only copies DECLARED
    fields off the ORM object, so created_by_username /
    reviewed_by_username can't be computed_field properties reading
    self.created_by / self.reviewed_by - that attribute is never
    actually present on the built model (see
    schemas/opening_inventory.py). Populated here instead, straight
    off the ORM relationship, before from_attributes runs.
    """

    response = OpeningInventorySetResponse.model_validate(
        inventory_set,
    )

    response.created_by_username = (
        inventory_set.created_by.username
        if inventory_set.created_by
        else None
    )
    response.reviewed_by_username = (
        inventory_set.reviewed_by.username
        if inventory_set.reviewed_by
        else None
    )

    return response


@router.get(
    "",
    response_model=list[OpeningInventorySetResponse],
    summary="List opening inventory sets",
)
def list_opening_inventory_sets(
    db: Session = Depends(get_db),
):
    return [
        _to_response(inventory_set)
        for inventory_set in get_opening_inventory_sets(db)
    ]


# Registered before GET /{set_id} on purpose - FastAPI matches routes
# in registration order, and /{set_id}'s int path param would
# otherwise greedily match the literal "active" and fail as an invalid
# integer (422). Same reasoning as GET /api/production-cycles/latest.
@router.get(
    "/active",
    response_model=OpeningInventoryStatusResponse,
    summary="Opening inventory review status",
)
def get_opening_inventory_status(
    db: Session = Depends(get_db),
):
    reviewed_set = get_reviewed_opening_inventory_set(db)
    draft_set = get_draft_opening_inventory_set(db)

    return OpeningInventoryStatusResponse(
        stock_validation_enabled=is_stock_validation_enabled(db),
        reviewed_set=(
            _to_response(reviewed_set)
            if reviewed_set is not None
            else None
        ),
        draft_set=(
            _to_response(draft_set) if draft_set is not None else None
        ),
    )


@router.get(
    "/{set_id}",
    response_model=OpeningInventorySetResponse,
)
def get_opening_inventory_set_by_id(
    set_id: int,
    db: Session = Depends(get_db),
):
    inventory_set = get_opening_inventory_set(db, set_id)

    if inventory_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opening inventory set not found",
        )

    return _to_response(inventory_set)


@router.post(
    "",
    response_model=OpeningInventorySetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_opening_inventory_set(
    data: OpeningInventorySetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _to_response(
            create_opening_inventory_set(db, data, current_user)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        # Defensive: schema validation and the service's own checks
        # (duplicate product, missing draft, unknown product id)
        # already catch the realistic cases as ValueError above. This
        # only guards against a constraint violation slipping past
        # those checks (e.g. a race on set_number) - either way, a
        # failed write must surface as a 4xx, never a raw 500.
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create this opening inventory set "
            "because of a conflicting record.",
        ) from exc


@router.patch(
    "/{set_id}",
    response_model=OpeningInventorySetResponse,
)
def update_existing_opening_inventory_set(
    set_id: int,
    data: OpeningInventorySetUpdate,
    db: Session = Depends(get_db),
):
    inventory_set = get_opening_inventory_set(db, set_id)

    if inventory_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opening inventory set not found",
        )

    try:
        return _to_response(
            update_opening_inventory_set(db, inventory_set, data)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update this opening inventory set "
            "because of a conflicting record.",
        ) from exc


@router.post(
    "/{set_id}/review",
    response_model=OpeningInventorySetResponse,
    summary="Mark an opening inventory set as reviewed",
)
def review_existing_opening_inventory_set(
    set_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inventory_set = get_opening_inventory_set(db, set_id)

    if inventory_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opening inventory set not found",
        )

    try:
        return _to_response(
            review_opening_inventory_set(
                db, inventory_set, current_user,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        # The partial unique index (uq_opening_inventory_single_
        # reviewed) is what would raise this - the service already
        # orders the supersede-then-review writes to avoid it under
        # normal operation, so reaching here means a concurrent review
        # raced this one. Either way, surface a 4xx, not a 500.
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not review this opening inventory set "
            "because another review happened at the same time.",
        ) from exc
