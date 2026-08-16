from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.resource import (
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)
from app.services.auth import get_current_user
from app.services.resource import (
    create_resource,
    delete_resource,
    get_resource,
    get_resources,
    update_resource,
)


router = APIRouter(
    prefix="/api/resources",
    tags=["Resources"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[ResourceResponse],
    summary="List active resources",
)
def list_resources(
    include_inactive: bool = Query(
        default=False,
        description="Include inactive resources in the results",
    ),
    db: Session = Depends(get_db),
):
    return get_resources(db, include_inactive)


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get resource by ID",
)
def get_resource_by_id(
    resource_id: int,
    db: Session = Depends(get_db),
):
    resource = get_resource(
        db,
        resource_id,
    )

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    return resource


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a resource",
)
def create_new_resource(
    resource_data: ResourceCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_resource(
            db,
            resource_data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update a resource",
)
def update_existing_resource(
    resource_id: int,
    resource_data: ResourceUpdate,
    db: Session = Depends(get_db),
):
    resource = get_resource(
        db,
        resource_id,
    )

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    try:
        return update_resource(
            db,
            resource,
            resource_data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a resource",
)
def delete_existing_resource(
    resource_id: int,
    db: Session = Depends(get_db),
):
    resource = get_resource(
        db,
        resource_id,
    )

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    delete_resource(
        db,
        resource,
    )