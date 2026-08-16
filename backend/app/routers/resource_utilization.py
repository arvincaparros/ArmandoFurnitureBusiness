from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.utilization import (
    ResourceUtilizationResponse,
    ResourceUtilizationRunResponse,
    ResourceUtilizationRunSummaryResponse,
)
from app.services.auth import get_current_user
from app.services.production import get_production_cycle
from app.services.resource_utilization import (
    calculate_resource_utilization,
    get_latest_production_cycle_id,
)
from app.services.resource_utilization_history import (
    get_resource_utilization_history,
    get_resource_utilization_history_run,
    summarize_utilization_run,
)


router = APIRouter(
    prefix="/api/resource-utilization",
    tags=["Resource Utilization"],
    dependencies=[Depends(get_current_user)],
)


# Registered before GET /{cycle_id} on purpose - same reasoning as
# production.py's /latest route: Starlette/FastAPI matches routes in
# registration order, and /{cycle_id}'s int path param would
# otherwise greedily match the literal "history" first and fail as an
# invalid integer (422) instead of reaching these routes.
@router.get(
    "/history",
    response_model=list[ResourceUtilizationRunSummaryResponse],
    summary="List resource utilization history snapshots",
)
def resource_utilization_history(
    cycle_id: int | None = None,
    db: Session = Depends(get_db),
):
    runs = get_resource_utilization_history(db, cycle_id)

    return [summarize_utilization_run(run) for run in runs]


@router.get(
    "/history/{run_id}",
    response_model=ResourceUtilizationRunResponse,
    summary="Get one resource utilization history snapshot in full",
)
def resource_utilization_history_detail(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = get_resource_utilization_history_run(db, run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource utilization history run not found",
        )

    return run


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
    cycle = get_production_cycle(
        db,
        cycle_id,
    )

    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production cycle not found",
        )

    return calculate_resource_utilization(db, cycle_id)
