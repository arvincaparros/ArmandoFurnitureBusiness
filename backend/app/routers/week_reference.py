from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.week_reference import (
    WeekReferenceCompareRequest,
    WeekReferenceCompareResponse,
    WeekReferenceSummaryResponse,
)
from app.services.auth import get_current_user
from app.services.week_reference import (
    WeekReferenceInfeasibleError,
    WeekReferenceNotFoundError,
    compare_week_reference,
    list_week_reference_summaries,
)

router = APIRouter(
    prefix="/api/week-references",
    tags=["Week Reference Verification"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[WeekReferenceSummaryResponse],
    summary="List the 8 official reference weeks",
)
def list_week_references():
    return list_week_reference_summaries()


@router.post(
    "/{week}/compare",
    response_model=WeekReferenceCompareResponse,
    summary="Run the actual solver against a reference week, optionally with resource overrides",
)
def compare_week(
    week: int,
    request: WeekReferenceCompareRequest,
):
    try:
        return compare_week_reference(week, request.resource_overrides)

    except WeekReferenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except WeekReferenceInfeasibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
