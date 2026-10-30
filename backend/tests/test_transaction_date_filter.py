"""
Window semantics for GET /api/transactions.

Kept in its own module because every test here asserts EXACT row
counts, which requires owning the whole sales_transactions table -
see the isolated_transactions fixture. test_transactions.py keeps
covering CRUD against a shared table with `any(...)`-style
assertions.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.database.models import Product, SalesTransaction


# The 10 sparse dates below are deliberately gappy, mirroring real
# furniture-shop data (a handful of sales a month, never daily). They
# are what separates the implemented rule - the 7 most recent dates
# that CONTAIN transactions - from the superficially similar "7
# calendar days counted back from the newest row", which on this data
# would return only the single Oct 14 row.
SPARSE_DATES = [
    date(2026, 8, 23),
    date(2026, 8, 27),
    date(2026, 8, 30),
    date(2026, 9, 5),
    date(2026, 9, 6),
    date(2026, 9, 16),
    date(2026, 9, 20),
    date(2026, 9, 28),
    date(2026, 10, 6),
    date(2026, 10, 14),
]

# The 7 most recent of SPARSE_DATES - i.e. everything from Sep 5 on.
SPARSE_EXPECTED_WINDOW_START = date(2026, 9, 5)


@pytest.fixture(autouse=True)
def isolated_transactions(db):
    """
    These tests assert exact counts, so each one owns the entire
    sales_transactions table.

    That is destructive, so it refuses to run anywhere except a
    database whose name marks it as throwaway. Pointing the suite at
    the development or production database would otherwise delete
    real sales history - and app/database/connection.py resolves
    DATABASE_URL from the environment, so a stray shell variable is
    all it would take.
    """

    database = db.get_bind().url.database or ""

    if not database.endswith("_test"):
        pytest.fail(
            "Refusing to run: this module deletes every row in "
            f"sales_transactions, but DATABASE_URL names '{database}', "
            "which is not a dedicated test database (expected a name "
            "ending in '_test')."
        )

    db.query(SalesTransaction).delete()
    db.commit()

    yield

    db.query(SalesTransaction).delete()
    db.commit()


@pytest.fixture
def filter_product(db):
    product = Product(
        name=f"Date Filter Product {uuid4().hex[:8]}",
        selling_price=Decimal("1000.00"),
        is_active=True,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    try:
        yield product

    finally:
        db.query(SalesTransaction).filter(
            SalesTransaction.product_id == product.id
        ).delete(synchronize_session=False)

        db.delete(product)
        db.commit()


def add_transaction(db, product, when):
    """
    `when` may be a date (stored at midnight, the shape the UI
    submits) or a full datetime (used to exercise the time-of-day
    boundary).
    """

    moment = (
        datetime.combine(when, datetime.min.time())
        if isinstance(when, date) and not isinstance(when, datetime)
        else when
    )

    transaction = SalesTransaction(
        transaction_number=f"TRX-F-{uuid4().hex[:10].upper()}",
        product_id=product.id,
        transaction_date=moment,
        quantity_produced=Decimal("1"),
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        total_sales=Decimal("100.00"),
        production_cost=Decimal("50.00"),
        unit_profit=Decimal("50.0000"),
        total_profit=Decimal("50.0000"),
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction


def returned_dates(payload):
    return [
        item["transaction_date"][:10] for item in payload["items"]
    ]


def iso(value):
    return value.isoformat()


# --------------------------------------------------------------------
# Default mode: the latest available window
# --------------------------------------------------------------------


def test_empty_table_returns_empty_state(client):
    response = client.get("/api/transactions")

    assert response.status_code == 200

    payload = response.json()

    assert payload["items"] == []
    assert payload["total"] == 0
    # No rows means there is no window to describe - the server does
    # not invent one around today.
    assert payload["range"] is None
    assert payload["available"] is None


def test_single_date_collapses_window_to_that_date(
    client,
    db,
    filter_product,
):
    add_transaction(db, filter_product, date(2026, 8, 10))

    payload = client.get("/api/transactions").json()

    assert payload["total"] == 1
    assert payload["range"]["start_date"] == "2026-08-10"
    assert payload["range"]["end_date"] == "2026-08-10"
    assert payload["range"]["mode"] == "latest_available"
    assert payload["available"] == {
        "earliest": "2026-08-10",
        "latest": "2026-08-10",
    }


def test_fewer_than_seven_dates_returns_everything(
    client,
    db,
    filter_product,
):
    dates = [
        date(2026, 8, 1),
        date(2026, 9, 15),
        date(2026, 10, 2),
    ]

    for day in dates:
        add_transaction(db, filter_product, day)

    payload = client.get("/api/transactions").json()

    assert payload["total"] == 3
    assert returned_dates(payload) == [iso(d) for d in dates]
    assert payload["range"]["start_date"] == "2026-08-01"
    assert payload["range"]["end_date"] == "2026-10-02"


def test_exactly_seven_dates_returns_everything(
    client,
    db,
    filter_product,
):
    dates = [date(2026, 10, day) for day in range(1, 8)]

    for day in dates:
        add_transaction(db, filter_product, day)

    payload = client.get("/api/transactions").json()

    assert payload["total"] == 7
    assert payload["range"]["start_date"] == "2026-10-01"
    assert payload["range"]["end_date"] == "2026-10-07"


def test_more_than_seven_dates_returns_latest_seven_only(
    client,
    db,
    filter_product,
):
    # 10 consecutive dates; the 3 oldest must fall outside the window.
    for day in range(1, 11):
        add_transaction(db, filter_product, date(2026, 10, day))

    payload = client.get("/api/transactions").json()

    assert payload["total"] == 7
    assert payload["range"]["start_date"] == "2026-10-04"
    assert payload["range"]["end_date"] == "2026-10-10"

    assert "2026-10-03" not in returned_dates(payload)

    # `available` still describes the whole table, not the window -
    # the two are deliberately different facts.
    assert payload["available"] == {
        "earliest": "2026-10-01",
        "latest": "2026-10-10",
    }


def test_sparse_dates_skip_gaps(client, db, filter_product):
    """
    The discriminating test for the chosen rule: with gappy data the
    window spans the 7 most recent dates that HAVE transactions, not
    the 7 calendar days preceding the newest row.
    """

    for day in SPARSE_DATES:
        add_transaction(db, filter_product, day)

    payload = client.get("/api/transactions").json()

    assert payload["total"] == 7
    assert (
        payload["range"]["start_date"]
        == iso(SPARSE_EXPECTED_WINDOW_START)
    )
    assert payload["range"]["end_date"] == "2026-10-14"

    # Present only under the data-anchored rule: a 7-calendar-day
    # window back from Oct 14 would start Oct 8 and drop both of
    # these, returning a single row.
    assert "2026-09-05" in returned_dates(payload)
    assert "2026-09-06" in returned_dates(payload)

    # The three August dates are the 8th, 9th and 10th most recent.
    for excluded in ("2026-08-23", "2026-08-27", "2026-08-30"):
        assert excluded not in returned_dates(payload)


def test_multiple_transactions_on_one_date_count_as_one_day(
    client,
    db,
    filter_product,
):
    # 7 distinct dates, with 3 rows sharing the newest one, plus an
    # 8th older date that must be pushed out. If same-date rows were
    # counted individually the window would stop short of Oct 1.
    for day in range(1, 8):
        add_transaction(db, filter_product, date(2026, 10, day))

    add_transaction(db, filter_product, date(2026, 10, 7))
    add_transaction(db, filter_product, date(2026, 10, 7))

    add_transaction(db, filter_product, date(2026, 9, 20))

    payload = client.get("/api/transactions").json()

    assert payload["range"]["start_date"] == "2026-10-01"
    assert payload["range"]["end_date"] == "2026-10-07"

    # 7 dates, one of which carries 3 rows.
    assert payload["total"] == 9
    assert returned_dates(payload).count("2026-10-07") == 3
    assert "2026-09-20" not in returned_dates(payload)


def test_end_of_day_row_on_boundary_date_is_included(
    client,
    db,
    filter_product,
):
    """
    transaction_date is a DateTime column. A row stored late in the
    day on the window's end date must still be returned - the reason
    the upper bound is half-open against the following midnight
    rather than a direct `<= end_date` comparison.
    """

    add_transaction(db, filter_product, date(2026, 10, 1))

    late = add_transaction(
        db,
        filter_product,
        datetime(2026, 10, 2, 23, 59, 59),
    )

    payload = client.get("/api/transactions").json()

    assert payload["range"]["end_date"] == "2026-10-02"
    assert late.id in [item["id"] for item in payload["items"]]
    assert payload["total"] == 2


def test_newly_added_latest_transaction_reanchors_window(
    client,
    db,
    filter_product,
):
    for day in range(1, 11):
        add_transaction(db, filter_product, date(2026, 10, day))

    newest = add_transaction(db, filter_product, date(2026, 11, 20))

    payload = client.get("/api/transactions").json()

    assert payload["range"]["end_date"] == "2026-11-20"
    assert payload["range"]["start_date"] == "2026-10-05"
    assert newest.id in [item["id"] for item in payload["items"]]


# --------------------------------------------------------------------
# Custom range mode
# --------------------------------------------------------------------


def test_custom_range_includes_both_endpoints(
    client,
    db,
    filter_product,
):
    for day in range(1, 11):
        add_transaction(db, filter_product, date(2026, 10, day))

    payload = client.get(
        "/api/transactions",
        params={
            "start_date": "2026-10-03",
            "end_date": "2026-10-05",
        },
    ).json()

    assert returned_dates(payload) == [
        "2026-10-03",
        "2026-10-04",
        "2026-10-05",
    ]
    assert payload["total"] == 3
    assert payload["range"] == {
        "start_date": "2026-10-03",
        "end_date": "2026-10-05",
        "mode": "custom",
    }


def test_custom_range_reaches_outside_the_default_window(
    client,
    db,
    filter_product,
):
    """
    A custom range is not clamped to the default window - it is how
    the user reaches older history without Show All.
    """

    for day in SPARSE_DATES:
        add_transaction(db, filter_product, day)

    payload = client.get(
        "/api/transactions",
        params={
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
        },
    ).json()

    assert returned_dates(payload) == [
        "2026-08-23",
        "2026-08-27",
        "2026-08-30",
    ]


def test_custom_range_start_date_only(
    client,
    db,
    filter_product,
):
    for day in range(1, 6):
        add_transaction(db, filter_product, date(2026, 10, day))

    payload = client.get(
        "/api/transactions",
        params={"start_date": "2026-10-04"},
    ).json()

    assert returned_dates(payload) == ["2026-10-04", "2026-10-05"]
    # The open bound is reported as null, not backfilled from the data.
    assert payload["range"] == {
        "start_date": "2026-10-04",
        "end_date": None,
        "mode": "custom",
    }


def test_custom_range_end_date_only(client, db, filter_product):
    for day in range(1, 6):
        add_transaction(db, filter_product, date(2026, 10, day))

    payload = client.get(
        "/api/transactions",
        params={"end_date": "2026-10-02"},
    ).json()

    assert returned_dates(payload) == ["2026-10-01", "2026-10-02"]
    assert payload["range"] == {
        "start_date": None,
        "end_date": "2026-10-02",
        "mode": "custom",
    }


def test_custom_range_with_no_matching_rows_is_empty_not_defaulted(
    client,
    db,
    filter_product,
):
    """
    An empty custom range must stay empty - it must not silently fall
    back to the default window, or the user could not tell that their
    chosen range has no data.
    """

    add_transaction(db, filter_product, date(2026, 10, 1))

    payload = client.get(
        "/api/transactions",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    ).json()

    assert payload["items"] == []
    assert payload["total"] == 0
    assert payload["range"]["mode"] == "custom"
    # `available` still tells the client real data exists elsewhere,
    # which is what lets the UI offer "Show All" from here.
    assert payload["available"] == {
        "earliest": "2026-10-01",
        "latest": "2026-10-01",
    }


def test_same_start_and_end_date_returns_that_day(
    client,
    db,
    filter_product,
):
    add_transaction(db, filter_product, date(2026, 10, 1))
    add_transaction(
        db,
        filter_product,
        datetime(2026, 10, 2, 18, 30),
    )
    add_transaction(db, filter_product, date(2026, 10, 3))

    payload = client.get(
        "/api/transactions",
        params={
            "start_date": "2026-10-02",
            "end_date": "2026-10-02",
        },
    ).json()

    assert payload["total"] == 1
    assert returned_dates(payload) == ["2026-10-02"]


def test_end_date_before_start_date_is_rejected(client):
    response = client.get(
        "/api/transactions",
        params={
            "start_date": "2026-10-10",
            "end_date": "2026-10-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "end_date must be greater than or equal to start_date"
    )


def test_malformed_date_is_rejected(client):
    response = client.get(
        "/api/transactions",
        params={"start_date": "2026-13-45"},
    )

    assert response.status_code == 422


# --------------------------------------------------------------------
# Show All mode
# --------------------------------------------------------------------


def test_show_all_returns_complete_history(
    client,
    db,
    filter_product,
):
    for day in SPARSE_DATES:
        add_transaction(db, filter_product, day)

    payload = client.get(
        "/api/transactions",
        params={"show_all": "true"},
    ).json()

    assert payload["total"] == len(SPARSE_DATES)
    # No window was applied, so there is none to report.
    assert payload["range"] is None
    assert payload["available"] == {
        "earliest": "2026-08-23",
        "latest": "2026-10-14",
    }


def test_show_all_false_behaves_as_default(
    client,
    db,
    filter_product,
):
    for day in SPARSE_DATES:
        add_transaction(db, filter_product, day)

    payload = client.get(
        "/api/transactions",
        params={"show_all": "false"},
    ).json()

    assert payload["total"] == 7
    assert payload["range"]["mode"] == "latest_available"


def test_show_all_combined_with_dates_is_rejected(client):
    response = client.get(
        "/api/transactions",
        params={
            "show_all": "true",
            "start_date": "2026-10-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "show_all cannot be combined with start_date or end_date"
    )


# --------------------------------------------------------------------
# Ordering, preserved across every mode
# --------------------------------------------------------------------


def test_ordering_is_preserved_in_every_mode(
    client,
    db,
    filter_product,
):
    # Two rows share a date so the (transaction_date, id) tie-break
    # is actually exercised, not just the date ordering.
    first_on_shared_date = add_transaction(
        db,
        filter_product,
        date(2026, 10, 5),
    )
    second_on_shared_date = add_transaction(
        db,
        filter_product,
        date(2026, 10, 5),
    )

    add_transaction(db, filter_product, date(2026, 10, 1))
    add_transaction(db, filter_product, date(2026, 10, 9))

    for params in (
        {},
        {"show_all": "true"},
        {"start_date": "2026-10-01", "end_date": "2026-10-09"},
    ):
        payload = client.get(
            "/api/transactions",
            params=params,
        ).json()

        dates = returned_dates(payload)

        assert dates == sorted(dates), (
            f"transaction_date ordering broken for params={params}"
        )

        shared = [
            item["id"]
            for item in payload["items"]
            if item["transaction_date"][:10] == "2026-10-05"
        ]

        assert shared == [
            first_on_shared_date.id,
            second_on_shared_date.id,
        ], f"id tie-break broken for params={params}"
