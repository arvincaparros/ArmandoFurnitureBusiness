from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.utilization import ResourceUtilizationResponse
from app.services.auth import get_current_user
from app.services.production import get_production_cycle
from app.services.resource_utilization import (
    calculate_resource_utilization,
    get_latest_production_cycle_id,
)


router = APIRouter(
    prefix="/api/resource-utilization",
    tags=["Resource Utilization"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=ResourceUtilizationResponse,
    summary="Get resource utilization for the latest production cycle",
)
def resource_utilization(
    db: Session = Depends(get_db),
):
    cycle_id = get_latest_production_cycle_id(db)

    if cycle_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No production cycles found",
        )

    return calculate_resource_utilization(db, cycle_id)


@router.get(
    "/{cycle_id}",
    response_model=ResourceUtilizationResponse,
    summary="Get resource utilization for a specific production cycle",
)
def resource_utilization_by_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    cycle = get_production_cycle(db, cycle_id)

    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production cycle not found",
        )

    return calculate_resource_utilization(db, cycle_id)
