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
from app.services.production_application import (
    get_cycle_consumed_by_resource,
    get_cycle_consumed_by_resource_since_update,
)
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

    # A cycle that has had production applications must report the
    # cumulative consumption those applications recorded, not what
    # the latest ProductionAllocation alone implies - otherwise the
    # report shows capacity the cycle has already spent.
    #
    # Scoped PER-RESOURCE to applications applied since that
    # resource's own quantity was last edited (see
    # get_cycle_consumed_by_resource_since_update's own docstring) -
    # a resource whose quantity was changed mid-cycle ("a new
    # production week") reports only consumption recorded under its
    # CURRENT quantity, not consumption accumulated under a
    # since-superseded one. A resource never edited keeps the same
    # all-time total get_cycle_consumed_by_resource would return.
    #
    # TWO genuinely different "empty" cases here, which must NOT be
    # treated alike:
    #
    #   1. This cycle has NEVER had a single ProductionApplication
    #      (get_cycle_consumed_by_resource - unscoped - is itself
    #      empty). There is no ledger to scope at all, so the
    #      ORIGINAL allocation-derived fallback (None, below) is
    #      still correct here - this is the pre-ledger/manual-
    #      allocation case (see _allocate() in
    #      test_resource_utilization.py), and must keep working
    #      exactly as it always has.
    #
    #   2. This cycle HAS applications, but every one of them
    #      predates its own resource's cutoff (every resource was
    #      just edited, "a new week started", and nothing has been
    #      applied since). The SCOPED dict is empty here too, but for
    #      a completely different reason - this is real, current
    #      ledger history being correctly excluded, not an absence of
    #      data. Passing None here (via a bare `consumed or None`)
    #      would fall through to the SAME allocation-derived branch
    #      as case 1 and silently resurrect the stale pre-edit plan's
    #      consumption - exactly the bug this scoping exists to fix.
    #      The scoped dict must be passed through AS-IS here, even
    #      though it's `{}` - calculate_resource_utilization already
    #      defaults any resource missing from an explicit override to
    #      zero on its own.
    has_any_application_ever = bool(
        get_cycle_consumed_by_resource(db, cycle_id)
    )

    consumed = (
        get_cycle_consumed_by_resource_since_update(db, cycle_id)
        if has_any_application_ever
        else None
    )

    return calculate_resource_utilization(
        db,
        cycle_id,
        consumption_override=consumed,
    )


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

    # A cycle that has had production applications must report the
    # cumulative consumption those applications recorded, not what
    # the latest ProductionAllocation alone implies - otherwise the
    # report shows capacity the cycle has already spent.
    #
    # Scoped PER-RESOURCE to applications applied since that
    # resource's own quantity was last edited (see
    # get_cycle_consumed_by_resource_since_update's own docstring) -
    # a resource whose quantity was changed mid-cycle ("a new
    # production week") reports only consumption recorded under its
    # CURRENT quantity, not consumption accumulated under a
    # since-superseded one. A resource never edited keeps the same
    # all-time total get_cycle_consumed_by_resource would return.
    #
    # TWO genuinely different "empty" cases here, which must NOT be
    # treated alike - see the identical comment in resource_utilization()
    # above for the full explanation:
    #
    #   1. This cycle has NEVER had a single ProductionApplication ->
    #      the ORIGINAL allocation-derived fallback (None) is still
    #      correct (the pre-ledger/manual-allocation case).
    #   2. This cycle HAS applications, but every one of them predates
    #      its own resource's cutoff ("a new week started", nothing
    #      applied since) -> the scoped dict must be passed through
    #      AS-IS, even though it's `{}`, never collapsed to None.
    has_any_application_ever = bool(
        get_cycle_consumed_by_resource(db, cycle_id)
    )

    consumed = (
        get_cycle_consumed_by_resource_since_update(db, cycle_id)
        if has_any_application_ever
        else None
    )

    return calculate_resource_utilization(
        db,
        cycle_id,
        consumption_override=consumed,
    )
