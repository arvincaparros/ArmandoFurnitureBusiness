from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import (
    OpeningInventoryItem,
    OpeningInventorySet,
    Product,
    User,
)
from app.schemas.opening_inventory import (
    OpeningInventorySetCreate,
    OpeningInventorySetUpdate,
)


# The only three values ever written to
# OpeningInventorySet.status. DRAFT is editable; REVIEWED is frozen
# and authoritative (at most one at a time, enforced by the
# uq_opening_inventory_single_reviewed partial index); SUPERSEDED is
# a previously-reviewed set that a later review replaced - kept, never
# deleted, so the declared-balance history stays auditable.
OPENING_INVENTORY_DRAFT = "DRAFT"
OPENING_INVENTORY_REVIEWED = "REVIEWED"
OPENING_INVENTORY_SUPERSEDED = "SUPERSEDED"


class OpeningInventoryRequiredError(Exception):
    """
    Raised when a sale is attempted before a complete REVIEWED
    opening inventory set exists.

    A distinct type rather than ValueError because the router has
    to answer 409 (the system is not in a state where this is
    allowed yet) rather than the 400 every other create-transaction
    failure returns. Nothing about the request is malformed - the
    precondition simply has not been met.
    """


def generate_opening_inventory_number(db: Session) -> str:
    """
    "OI-0001", "OI-0002", ... - same sequential friendly-id convention
    as transaction.py::generate_transaction_number and
    resource_utilization_history.py::generate_utilization_number,
    rather than the model's random-hex fallback default.
    """

    last_id = db.scalar(
        select(func.max(OpeningInventorySet.id))
    )

    return f"OI-{(last_id or 0) + 1:04d}"


def get_opening_inventory_sets(
    db: Session,
) -> list[OpeningInventorySet]:
    statement = (
        select(OpeningInventorySet)
        .options(
            selectinload(OpeningInventorySet.items),
        )
        .order_by(
            OpeningInventorySet.created_at.desc(),
            OpeningInventorySet.id.desc(),
        )
    )

    return list(db.scalars(statement).all())


def get_opening_inventory_set(
    db: Session,
    set_id: int,
) -> OpeningInventorySet | None:
    return db.get(OpeningInventorySet, set_id)


def get_reviewed_opening_inventory_set(
    db: Session,
) -> OpeningInventorySet | None:
    """
    "The" reviewed set, singular, is guaranteed by the
    uq_opening_inventory_single_reviewed partial unique index - this
    never has to disambiguate between two.
    """

    statement = (
        select(OpeningInventorySet)
        .options(selectinload(OpeningInventorySet.items))
        .where(
            OpeningInventorySet.status
            == OPENING_INVENTORY_REVIEWED
        )
        .limit(1)
    )

    return db.scalar(statement)


def get_draft_opening_inventory_set(
    db: Session,
) -> OpeningInventorySet | None:
    statement = (
        select(OpeningInventorySet)
        .options(selectinload(OpeningInventorySet.items))
        .where(
            OpeningInventorySet.status == OPENING_INVENTORY_DRAFT
        )
        .order_by(
            OpeningInventorySet.created_at.desc(),
            OpeningInventorySet.id.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)


def is_stock_validation_enabled(db: Session) -> bool:
    """
    The gate - and it is a PRECONDITION FOR SELLING AT ALL, not a
    permission to validate. False means sales are refused (409), not
    that they are accepted unvalidated: accepting them would let true
    stock go negative during setup, which the derived figure's
    zero-floor would then hide rather than prevent.

    Checking only that a REVIEWED set EXISTS is sufficient because
    review refuses an incomplete declaration (see
    find_missing_opening_declarations), so a REVIEWED set is complete
    by construction.
    """

    return (
        db.scalar(
            select(func.count(OpeningInventorySet.id)).where(
                OpeningInventorySet.status
                == OPENING_INVENTORY_REVIEWED
            )
        )
        or 0
    ) > 0


def get_opening_quantities(db: Session) -> dict[int, Decimal]:
    """
    product_id -> declared opening balance, from the REVIEWED set
    only.

    A product absent from this dict opens at zero, but that is NOT
    the same as "a missing row means zero": review refuses a set
    that omits any applicable product, so the only products missing
    here are ones created after the set's effective_date, which have
    no pre-existing stock by construction. An empty dict means no
    REVIEWED set exists yet - and in that state sales are refused
    outright, so no stock figure is derived from it.
    """

    reviewed_set = get_reviewed_opening_inventory_set(db)

    if reviewed_set is None:
        return {}

    return {
        item.product_id: item.quantity
        for item in reviewed_set.items
    }


def get_products_requiring_opening_declaration(
    db: Session,
    effective_date: datetime,
) -> list[Product]:
    """
    The products a set must declare to count as complete: ACTIVE
    products that already existed on the effective date.

    Both halves are deliberate. Inactive products are retired (the
    product delete path is a soft delete), so requiring a
    declaration for them would block review forever on historical
    clutter. A product created AFTER the effective date cannot have
    had pre-existing stock on that date, so it opens at zero by
    construction rather than by silence - and requiring it would
    mean every new product blocked all sales until someone reviewed
    a fresh set.
    """

    return list(
        db.scalars(
            select(Product)
            .where(
                Product.is_active.is_(True),
                Product.created_at <= effective_date,
            )
            .order_by(Product.name)
        ).all()
    )


def find_missing_opening_declarations(
    db: Session,
    inventory_set: OpeningInventorySet,
) -> list[Product]:
    """
    Applicable products this set does NOT declare. Empty list means
    the set is complete and may be reviewed.

    An explicit zero counts as a declaration; only an ABSENT row is
    missing. That distinction is the whole point - a missing row is
    an incomplete declaration, never an implied zero.
    """

    declared = {
        item.product_id
        for item in inventory_set.items
    }

    return [
        product
        for product in (
            get_products_requiring_opening_declaration(
                db,
                inventory_set.effective_date,
            )
        )
        if product.id not in declared
    ]


def _replace_items(
    db: Session,
    inventory_set: OpeningInventorySet,
    items,
) -> None:
    db.query(OpeningInventoryItem).filter(
        OpeningInventoryItem.opening_inventory_set_id
        == inventory_set.id
    ).delete(synchronize_session=False)

    for item in items:
        product = db.get(Product, item.product_id)

        if product is None:
            raise ValueError(
                f"Product {item.product_id} not found"
            )

        db.add(
            OpeningInventoryItem(
                opening_inventory_set_id=inventory_set.id,
                product_id=item.product_id,
                quantity=item.quantity,
                notes=item.notes,
            )
        )


def create_opening_inventory_set(
    db: Session,
    data: OpeningInventorySetCreate,
    user: User,
) -> OpeningInventorySet:
    """
    Always created as DRAFT - there is no "create already reviewed"
    path, because the review is a deliberate second human action and
    the whole point of the gate.
    """

    existing_draft = get_draft_opening_inventory_set(db)

    if existing_draft is not None:
        raise ValueError(
            "A draft opening inventory set already exists "
            f"({existing_draft.set_number}). Edit or review it "
            "instead of creating another."
        )

    inventory_set = OpeningInventorySet(
        set_number=generate_opening_inventory_number(db),
        status=OPENING_INVENTORY_DRAFT,
        effective_date=data.effective_date,
        notes=data.notes,
        created_by_user_id=user.id,
    )

    try:
        db.add(inventory_set)
        db.flush()

        _replace_items(db, inventory_set, data.items)

        db.commit()
        db.refresh(inventory_set)

        return inventory_set

    except Exception:
        db.rollback()
        raise


def update_opening_inventory_set(
    db: Session,
    inventory_set: OpeningInventorySet,
    data: OpeningInventorySetUpdate,
) -> OpeningInventorySet:
    if inventory_set.status != OPENING_INVENTORY_DRAFT:
        raise ValueError(
            "This opening inventory set has already been reviewed "
            "and can no longer be edited. Create a new set to "
            "correct the balances."
        )

    update_data = data.model_dump(exclude_unset=True)

    if "effective_date" in update_data:
        inventory_set.effective_date = update_data[
            "effective_date"
        ]

    if "notes" in update_data:
        inventory_set.notes = update_data["notes"]

    try:
        if data.items is not None:
            _replace_items(db, inventory_set, data.items)

        db.commit()
        db.refresh(inventory_set)

        return inventory_set

    except Exception:
        db.rollback()
        raise


def review_opening_inventory_set(
    db: Session,
    inventory_set: OpeningInventorySet,
    user: User,
) -> OpeningInventorySet:
    """
    DRAFT -> REVIEWED, demoting any currently-reviewed set to
    SUPERSEDED in the SAME transaction. Both happen together or
    neither does: the uq_opening_inventory_single_reviewed partial
    index would reject the insert half of a split attempt anyway, so
    doing it in one transaction turns a potential IntegrityError into
    a correct outcome.
    """

    if inventory_set.status == OPENING_INVENTORY_REVIEWED:
        raise ValueError(
            "This opening inventory set has already been reviewed."
        )

    if inventory_set.status != OPENING_INVENTORY_DRAFT:
        raise ValueError(
            "Only a draft opening inventory set can be reviewed."
        )

    if not inventory_set.items:
        raise ValueError(
            "Declare at least one product's opening balance before "
            "reviewing this set."
        )

    # Completeness is enforced HERE, at review, so that everything
    # downstream can treat "a REVIEWED set exists" as "a complete
    # declaration exists". Doing it at sale time instead would mean
    # re-deriving the applicable product list on every transaction.
    missing = find_missing_opening_declarations(db, inventory_set)

    if missing:
        raise ValueError(
            "Every active product that existed on this set's "
            "effective date needs an explicit opening quantity, "
            "including zero. Not yet declared: "
            + ", ".join(product.name for product in missing)
        )

    previous = get_reviewed_opening_inventory_set(db)

    try:
        if previous is not None:
            previous.status = OPENING_INVENTORY_SUPERSEDED
            db.flush()

        inventory_set.status = OPENING_INVENTORY_REVIEWED
        inventory_set.reviewed_at = datetime.utcnow()
        inventory_set.reviewed_by_user_id = user.id

        db.commit()
        db.refresh(inventory_set)

        return inventory_set

    except Exception:
        db.rollback()
        raise
