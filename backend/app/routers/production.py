from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.production import (
    ProductionCycleCreate,
    ProductionCycleResponse,
    ProductionCycleUpdate,
)
from app.schemas.feasibility import (
    ProductionFeasibilityResponse,
)
from app.schemas.production_application import (
    ProductionApplicationResponse,
)
from app.services.production_application import (
    get_applications,
    get_cycle_consumed_by_resource,
)
from app.services.production import (
    create_production_cycle,
    delete_production_cycle,
    get_latest_production_cycle,
    get_production_cycle,
    get_production_cycles,
    update_production_cycle,
)

from app.services.production_calculation import (
    calculate_resource_consumption,
    check_allocation_feasibility,
)

from app.schemas.optimization import (
    OptimizationRequest,
    OptimizationResponse,
    PlanningMode,
)

from datetime import datetime

from app.services.optimization import (
    get_optimization_data,
    solve_optimization,
    build_optimization_result,
    apply_optimization,
    validate_minimum_demand_resource_availability,
)

from app.services.optimization_history import (
    save_optimization_history,
)

from app.services.forecasting import get_forecast

from app.services.auth import get_current_user

router = APIRouter(
    prefix="/api/production-cycles",
    tags=["Production Cycles"],
    dependencies=[Depends(get_current_user)],
)

@router.get(
    "",
    response_model=list[ProductionCycleResponse],
    summary="List production cycles",
)
def list_production_cycles(
    db: Session = Depends(get_db),
):
    return get_production_cycles(db)


# Registered before GET /{cycle_id} on purpose - Starlette/FastAPI
# matches routes in registration order, and /{cycle_id}'s int path
# param would otherwise greedily match the literal "latest" first
# and fail as an invalid integer (422) instead of reaching this
# route.
@router.get(
    "/latest",
    response_model=ProductionCycleResponse,
    summary="Get the latest production cycle",
)
def get_latest_production_cycle_endpoint(
    db: Session = Depends(get_db),
):
    cycle = get_latest_production_cycle(db)

    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No production cycle found",
        )

    return cycle

@router.post(
    "",
    response_model=ProductionCycleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a production cycle",
)
def create_new_production_cycle(
    cycle_data: ProductionCycleCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_production_cycle(
            db,
            cycle_data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{cycle_id}",
    response_model=ProductionCycleResponse,
    summary="Update a production cycle",
)
def update_existing_production_cycle(
    cycle_id: int,
    cycle_data: ProductionCycleUpdate,
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

    try:
        return update_production_cycle(
            db,
            cycle,
            cycle_data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

@router.delete(
    "/{cycle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a production cycle",
)
def delete_existing_production_cycle(
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

    try:
        delete_production_cycle(
            db,
            cycle,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

@router.post(
    "/{cycle_id}/optimize",
    response_model=OptimizationResponse,
    summary="Optimize production plan",
)
def optimize_production(
    cycle_id: int,
    optimization_data: OptimizationRequest,
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

    data = get_optimization_data(
        db,
        cycle_id,
    )

    if not data["cycle_resources"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Production cycle has no resources configured",
        )

    # Two planning modes, same solver call below - only this `forecast`
    # value differs between them. demand_based (default) builds the
    # exact same dict this always has; resource_based passes None so
    # add_forecast_constraints() never runs and no product is capped by
    # sales forecast - every other constraint (resource availability,
    # BOM, minimum demand, profit objective) is untouched either way,
    # since both modes call the identical solve_optimization().
    if optimization_data.planning_mode == PlanningMode.RESOURCE_BASED:
        forecast = None
    else:
        forecast_data = get_forecast(db)

        forecast = {
            item["product_id"]: item["forecast_quantity"]
            for item in forecast_data["products"]
            if item["forecast_quantity"] > 0
        }

    started_at = datetime.now()

    # Generate must return an independent, repeatable proposal based
    # on this cycle's CURRENT declared resource capacities - never
    # shrunk by what earlier applications in this same cycle have
    # already consumed. That protection belongs to apply_optimization
    # alone, which re-derives and revalidates this same figure for
    # itself at Apply time (see its own get_cycle_consumed_by_resource
    # call) - a plan Generate is happy to propose can still be
    # correctly rejected there if the cycle doesn't actually have that
    # much left. Computed here only for the utilization/bottleneck
    # preview below (build_optimization_result), so that preview can
    # still honestly show >100% utilization when this fresh proposal,
    # combined with what's already consumed, would exceed capacity -
    # it just no longer shrinks the proposal itself.
    already_consumed_by_resource_id = get_cycle_consumed_by_resource(
        db,
        cycle_id,
    )

    try:
        # Revision #3: the one minimum-demand pre-solve check that
        # needs a fresh DB query (a product's COMPLETE requirement
        # list, not the cycle-resource-filtered data["requirements"]
        # above) runs here, before solve_optimization - see its
        # docstring for why it can't just reuse `data`.
        validate_minimum_demand_resource_availability(
            db,
            cycle_id,
        )

        result = solve_optimization(
            cycle_id,
            data["products"],
            data["cycle_resources"],
            data["requirements"],
            optimization_data.objective.value,
            forecast=forecast,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    completed_at = datetime.now()

    # Computed once, before the save below, so the persisted
    # total_cost snapshot and the total_cost returned in this same
    # response are guaranteed to be the exact same figure - never two
    # independent calculations that could drift from each other.
    optimization_result = build_optimization_result(
        cycle_id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        result["allocations"],
        result["status"],
        already_consumed_by_resource_id,
    )

    save_optimization_history(
        db=db,
        cycle_id=cycle_id,
        started_at=started_at,
        completed_at=completed_at,
        result=result,
        total_cost=optimization_result["total_cost"],
    )

    # Not persisted (see PlanningMode/OptimizationResponse's own notes) -
    # only this fresh response reports which mode produced it.
    optimization_result["planning_mode"] = (
        optimization_data.planning_mode.value
    )

    return optimization_result

@router.post(
    "/{cycle_id}/optimize/apply",
    response_model=OptimizationResponse,
    summary="Apply optimized production plan",
)
def apply_production_optimization(
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

    try:
        return apply_optimization(
            db,
            cycle_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

@router.get(
    "/{cycle_id}/resource-consumption",
    summary="Calculate resource consumption",
)
def get_resource_consumption(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    try:
        return calculate_resource_consumption(
            db,
            cycle_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    
@router.get(
    "/{cycle_id}/feasibility",
    response_model=ProductionFeasibilityResponse,
    summary="Check production feasibility",
)
def get_production_feasibility(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    try:
        return check_allocation_feasibility(
            db,
            cycle_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

@router.get(
    "/{cycle_id}/applications",
    response_model=list[ProductionApplicationResponse],
    summary="List production applications for a cycle",
)
def list_production_applications(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    return get_applications(db, cycle_id)


@router.get(
    "/{cycle_id}",
    response_model=ProductionCycleResponse,
    summary="Get production cycle by ID",
)
def get_production_cycle_by_id(
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

    return cycle