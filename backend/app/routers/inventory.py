from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.inventory import InventoryOverviewResponse
from app.services.auth import get_current_user
from app.services.inventory import get_inventory_overview


router = APIRouter(
    prefix="/api/inventory",
    tags=["Inventory"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=InventoryOverviewResponse,
    summary="Available stock and cycle production/sales totals",
)
def get_inventory(
    db: Session = Depends(get_db),
):
    return get_inventory_overview(db)
