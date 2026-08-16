from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.optimization_history import (
    OptimizationHistoryResponse,
)
from app.services.auth import get_current_user
from app.services.optimization_history import (
    get_optimization_history,
    get_optimization_history_run,
)


router = APIRouter(
    prefix="/api/optimization",
    tags=["Optimization"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/history",
    response_model=list[OptimizationHistoryResponse],
)
def list_optimization_history(
    cycle_id: int | None = None,
    db: Session = Depends(get_db),
):
    return get_optimization_history(
        db,
        cycle_id,
    )


@router.get(
    "/history/{run_id}",
    response_model=OptimizationHistoryResponse,
)
def get_optimization_history_detail(
    run_id: int,
    db: Session = Depends(get_db),
):
    optimization_run = get_optimization_history_run(
        db,
        run_id,
    )

    if optimization_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Optimization run not found",
        )

    return optimization_run