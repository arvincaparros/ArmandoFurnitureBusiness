# Deferred: `forecast_results.product_id` FK drift (model says CASCADE, database says NO ACTION)

**Status:** DEFERRED — recorded only. Nothing changed, no migration written, no migration run. Explicitly out of scope of the test-fixture purge work it was found during (2026-10-31), and deliberately left for a separate investigation with its own approval.

**Found during:** centralizing the test-fixture ledger purge in `backend/tests/conftest.py`. Discovered while enumerating every foreign key in `armando_furniture_test` to confirm the four intended `ON DELETE RESTRICT` constraints were unchanged — this drift was an incidental finding, not the thing being looked for.

## The discrepancy

`app/database/models.py` (`ForecastResult.product_id`, ~line 707) declares:

```python
product_id: Mapped[int] = mapped_column(
    ForeignKey(
        "products.id",
        ondelete="CASCADE",
    ),
    nullable=False,
    index=True,
)
```

The live constraint in `armando_furniture_test` is `NO ACTION`:

```
CHILD              COLUMN      PARENT     ON DELETE
forecast_results   product_id  products   NO ACTION
```

Every other FK in the schema matches its model declaration. This is the only mismatch found. All 26 foreign keys were enumerated; the four intended RESTRICT constraints
(`production_applications.production_cycle_id`, `production_applications.optimization_run_id`,
`production_application_items.product_id`, `opening_inventory_items.product_id`)
are present and correct.

## Why it matters

`NO ACTION` and `CASCADE` have opposite effects on a product delete:

- **CASCADE** (what the model claims): deleting a product silently deletes its forecast rows.
- **NO ACTION** (what the database does): deleting a product is *refused* if any forecast row references it.

So a `DELETE` on a product with forecast history fails today, while the model says it should succeed. `NO ACTION` behaves like `RESTRICT` here in practice; the difference between them is only that `NO ACTION` defers the check to end-of-statement and so can be satisfied by a deferred constraint or a same-statement cleanup, whereas `RESTRICT` cannot.

Two consequences worth confirming in the separate investigation:

1. **A latent test-teardown hazard.** Fixtures that delete products (`test_products` in `conftest.py`) would raise `IntegrityError` on teardown if a forecast row still pointed at a fixture product. This does not happen today only because the forecast suites clean up their own rows. It is a hidden dependency on test cleanup order, not a guarantee.
2. **Unknown production behavior.** Whether any product-delete path can reach this FK, and whether CASCADE or RESTRICT is the *correct* business rule for forecast history, is an open question. Note that the comparable history tables deliberately chose RESTRICT (`opening_inventory_items.product_id`, `production_application_items.product_id`) with the documented reasoning that history must outlive the product. If that reasoning applies to forecast results too, then the **database is currently right and the model is wrong** — which would make this a model correction rather than a migration.

## Not yet established

- Which of the two is intended. Do not assume the model is authoritative.
- How the drift arose — whether the table predates the `ondelete` declaration, or a migration omitted it. Not investigated; no migration history was read.
- Whether the development database (`armando_furniture`) shows the same drift. **Only `armando_furniture_test` was inspected.** The development database was deliberately never connected to during this work.

## Suggested first step for the separate investigation

Read-only: compare this FK across `armando_furniture` and `armando_furniture_test`, then read the migration history for `forecast_results` to find where the `ondelete` was lost or never applied. Decide the intended semantics against the RESTRICT reasoning already documented on the other history tables **before** writing anything.
