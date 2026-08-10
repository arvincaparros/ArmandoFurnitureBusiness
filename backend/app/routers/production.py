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
from app.services.production import (
    create_production_cycle,
    delete_production_cycle,
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
)

from datetime import datetime

from app.services.optimization import (
    get_optimization_data,
    solve_optimization,
    build_optimization_result,
    apply_optimization,
)

from app.services.optimization_history import (
    save_optimization_history,
)

from app.services.forecasting import get_forecast

router = APIRouter(
    prefix="/api/production-cycles",
    tags=["Production Cycles"],
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

    delete_production_cycle(
        db,
        cycle,
    )

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

    forecast_data = get_forecast(db)

    forecast = {
        item["product_id"]: item["forecast_quantity"]
        for item in forecast_data["products"]
        if item["forecast_quantity"] > 0
    }
    
    started_at = datetime.now()

    try:
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

    save_optimization_history(
        db=db,
        cycle_id=cycle_id,
        started_at=started_at,
        completed_at=completed_at,
        result=result,
    )

    return build_optimization_result(
        cycle_id,
        data["products"],
        data["cycle_resources"],
        data["requirements"],
        result["allocations"],
        result["status"],
    )

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