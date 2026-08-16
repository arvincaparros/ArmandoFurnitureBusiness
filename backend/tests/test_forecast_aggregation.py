from datetime import datetime
from decimal import Decimal

from app.database.models import SalesTransaction
from app.services.forecasting import get_monthly_historical_demand


def _make_transaction(product_id, transaction_date, quantity):
    quantity = Decimal(str(quantity))

    return SalesTransaction(
        product_id=product_id,
        transaction_date=transaction_date,
        quantity_produced=quantity,
        quantity=quantity,
        unit_price=Decimal("10.00"),
        total_sales=quantity * Decimal("10.00"),
        production_cost=Decimal("0.00"),
        unit_profit=Decimal("0.00"),
        total_profit=Decimal("0.00"),
    )


def _add_transactions(db, transactions):
    db.add_all(transactions)
    db.commit()

    for transaction in transactions:
        db.refresh(transaction)

    return transactions


def _cleanup(db, transactions):
    for transaction in transactions:
        db.delete(transaction)

    db.commit()


def test_multiple_transactions_same_month_are_summed(
    db,
    test_products,
):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product.id, datetime(2026, 1, 5), "10"
            ),
            _make_transaction(
                product.id, datetime(2026, 1, 25), "5"
            ),
        ],
    )

    try:
        result = get_monthly_historical_demand(db)
        series = result[product.id]

        assert series == [
            {"period": "2026-01", "quantity": Decimal("15")},
        ]

    finally:
        _cleanup(db, transactions)


def test_multiple_months_are_separated(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product.id, datetime(2026, 1, 10), "10"
            ),
            _make_transaction(
                product.id, datetime(2026, 2, 10), "20"
            ),
        ],
    )

    try:
        result = get_monthly_historical_demand(db)
        series = result[product.id]

        assert series == [
            {"period": "2026-01", "quantity": Decimal("10")},
            {"period": "2026-02", "quantity": Decimal("20")},
        ]

    finally:
        _cleanup(db, transactions)


def test_missing_month_is_zero_filled(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product.id, datetime(2026, 1, 10), "15"
            ),
            _make_transaction(
                product.id, datetime(2026, 3, 5), "8"
            ),
            _make_transaction(
                product.id, datetime(2026, 3, 18), "12"
            ),
            _make_transaction(
                product.id, datetime(2026, 4, 2), "18"
            ),
        ],
    )

    try:
        result = get_monthly_historical_demand(db)
        series = result[product.id]

        assert series == [
            {"period": "2026-01", "quantity": Decimal("15")},
            {"period": "2026-02", "quantity": Decimal("0")},
            {"period": "2026-03", "quantity": Decimal("20")},
            {"period": "2026-04", "quantity": Decimal("18")},
        ]

    finally:
        _cleanup(db, transactions)


def test_inactive_product_excluded(db, test_products):
    product = test_products[0]
    product.is_active = False
    db.commit()

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product.id, datetime(2026, 1, 10), "10"
            ),
        ],
    )

    try:
        result = get_monthly_historical_demand(db)

        assert product.id not in result

    finally:
        _cleanup(db, transactions)
        product.is_active = True
        db.commit()


def test_non_positive_quantity_excluded(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product.id, datetime(2026, 1, 10), "0"
            ),
            _make_transaction(
                product.id, datetime(2026, 2, 10), "5"
            ),
        ],
    )

    try:
        result = get_monthly_historical_demand(db)
        series = result[product.id]

        # The zero-quantity transaction is excluded entirely, so
        # the series starts at February (no January entry at all,
        # not even a zero-filled one) since it is outside the
        # qualifying first-to-last transaction span.
        assert series == [
            {"period": "2026-02", "quantity": Decimal("5")},
        ]

    finally:
        _cleanup(db, transactions)


def test_chronological_ordering(db, test_products):
    product = test_products[0]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product.id, datetime(2026, 3, 1), "3"
            ),
            _make_transaction(
                product.id, datetime(2026, 1, 1), "1"
            ),
            _make_transaction(
                product.id, datetime(2026, 2, 1), "2"
            ),
        ],
    )

    try:
        result = get_monthly_historical_demand(db)
        series = result[product.id]

        periods = [item["period"] for item in series]

        assert periods == ["2026-01", "2026-02", "2026-03"]

    finally:
        _cleanup(db, transactions)


def test_product_isolation(db, test_products):
    product_a = test_products[0]
    product_b = test_products[1]

    transactions = _add_transactions(
        db,
        [
            _make_transaction(
                product_a.id, datetime(2026, 1, 10), "10"
            ),
            _make_transaction(
                product_b.id, datetime(2026, 1, 10), "99"
            ),
            _make_transaction(
                product_b.id, datetime(2026, 2, 10), "1"
            ),
        ],
    )

    try:
        result = get_monthly_historical_demand(db)

        assert result[product_a.id] == [
            {"period": "2026-01", "quantity": Decimal("10")},
        ]

        assert result[product_b.id] == [
            {"period": "2026-01", "quantity": Decimal("99")},
            {"period": "2026-02", "quantity": Decimal("1")},
        ]

    finally:
        _cleanup(db, transactions)
