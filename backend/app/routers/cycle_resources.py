from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.production import (
    CycleResourceCreate,
    CycleResourceResponse,
    CycleResourceUpdate,
)
from app.services.auth import get_current_user
from app.services.cycle_resource import (
    create_cycle_resource,
    delete_cycle_resource,
    get_cycle_resource,
    get_cycle_resources,
    update_cycle_resource,
)


router = APIRouter(
    prefix="/api/production-cycles/{cycle_id}/resources",
    tags=["Cycle Resources"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[CycleResourceResponse],
    summary="List resources for a production cycle",
)
def list_cycle_resources(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    return get_cycle_resources(
        db,
        cycle_id,
    )


@router.post(
    "",
    response_model=CycleResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a resource to a production cycle",
)
def create_new_cycle_resource(
    cycle_id: int,
    data: CycleResourceCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_cycle_resource(
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
    "/{resource_id}",
    response_model=CycleResourceResponse,
    summary="Update a cycle resource",
)
def update_existing_cycle_resource(
    cycle_id: int,
    resource_id: int,
    data: CycleResourceUpdate,
    db: Session = Depends(get_db),
):
    cycle_resource = get_cycle_resource(
        db,
        cycle_id,
        resource_id,
    )

    if cycle_resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle resource not found",
        )

    return update_cycle_resource(
        db,
        cycle_resource,
        data,
    )


@router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a resource from a production cycle",
)
def delete_existing_cycle_resource(
    cycle_id: int,
    resource_id: int,
    db: Session = Depends(get_db),
):
    cycle_resource = get_cycle_resource(
        db,
        cycle_id,
        resource_id,
    )

    if cycle_resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle resource not found",
        )

    delete_cycle_resource(
        db,
        cycle_resource,
    )
    