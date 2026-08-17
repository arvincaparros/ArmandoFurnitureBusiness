from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import (
    CycleResource,
    ForecastResult,
    ForecastRun,
    OptimizationResult,
    OptimizationRun,
    Product,
    ProductResourceRequirement,
    ProductionAllocation,
    ProductionCycle,
    Resource,
    SalesTransaction,
)


def reset_demo_data(db: Session) -> None:
    """
    Clears all business/demo data in FK-safe (child-before-parent)
    order, so it works via bulk deletes regardless of any individual
    ondelete=CASCADE config - never assumes cascade will do the work.
    Never touches the `users` table (authentication) or Alembic's own
    migration metadata table - only the tables this function names.
    """

    db.query(OptimizationResult).delete()
    db.query(OptimizationRun).delete()
    db.query(ProductionAllocation).delete()
    db.query(ForecastResult).delete()
    db.query(ForecastRun).delete()
    db.query(SalesTransaction).delete()
    db.query(CycleResource).delete()
    db.query(ProductResourceRequirement).delete()
    db.query(ProductionCycle).delete()
    db.query(Product).delete()
    db.query(Resource).delete()

    db.commit()


def seed_database() -> None:
    """
    Client cost-model reconciliation (Phase 1): resources, products,
    BOM, and cycle prices below are reverse-engineered/verified
    directly from the client's reference spreadsheet (11 products,
    resource weekly-price table, and per-product total-cost/profit
    figures), not invented demo values. See the reconciliation report
    for the full derivation - in particular:

    - Wood's true rate is ₱84/BF, not the ₱8.40/BF naively implied by
      weekly_price / availability - confirmed by isolating wood's
      contribution across the four Door products, which only differ
      from each other in wood quantity.
    - Doorknob & Hinge is ₱300/set - this is the client's stated unit
      price directly, NOT weekly_price / availability (300 / 13 =
      ₱23.08 was an earlier, incorrect interpretation: the 13 is only
      the weekly quantity available, not a divisor for the price).
    - Circular Saw and Table Planer are BOTH ₱31.56912/hr, and Hand
      Planer is exactly half that (₱15.78456/hr) - solved exactly by
      reconciling all 11 products' reference total cost against their
      machine-hour requirements (a 3-equation/3-unknown system, since
      only 3 distinct machine-hour profiles exist across the 11
      products). This is NOT weekly_price / availability per machine
      independently - that naive approach (₱31.5685/hr, ₱31.5692/hr,
      ₱3.1569/hr) was the actual root cause of an earlier ~₱12.62 (and
      ~₱6.31 on doors) discrepancy per product, not a precision issue.
      Rounded to centavos here (₱31.57, ₱31.57, ₱15.78) because
      CycleResource.unit_price is Numeric(12, 2) - exact reproduction
      of the spreadsheet's 5-decimal figures needs 5 decimal places
      of precision (e.g. 15.78456), which this column does not carry;
      the resulting drift is at most ~₱0.002 per product, confirmed
      by direct computation, not assumed.
    - Labor cost does NOT reduce to labor_hours x a shared rate (two
      products can share identical hours and identical BOM but have
      different total cost) - each product's labor_cost below is
      seeded directly from the client's own per-product figure
      instead (see Product.labor_cost).
    """

    db = SessionLocal()

    try:
        # -------------------------
        # Resources
        # -------------------------

        wood = Resource(name="Wood", resource_type="material", unit="BF")
        epoxy = Resource(name="Epoxy", resource_type="material", unit="L")
        nails = Resource(name="Nails", resource_type="material", unit="kg")
        wood_glue = Resource(name="Wood Glue", resource_type="material", unit="L")
        sandpaper = Resource(name="Sandpaper", resource_type="material", unit="pcs")
        doorknob = Resource(name="Doorknob & Hinge", resource_type="material", unit="sets")
        labor = Resource(name="Labor", resource_type="labor", unit="hours")
        circular_saw = Resource(name="Circular Saw", resource_type="machine", unit="hours")
        table_planer = Resource(name="Table Planer", resource_type="machine", unit="hours")
        hand_planer = Resource(name="Hand Planer", resource_type="machine", unit="hours")

        db.add_all([
            wood, epoxy, nails, wood_glue, sandpaper, doorknob,
            labor, circular_saw, table_planer, hand_planer,
        ])

        # -------------------------
        # Products (client reference catalog - x1 to x11)
        # -------------------------

        dining_table_4 = Product(name="Dining Table (4 seater)", selling_price=Decimal("18000.00"), labor_cost=Decimal("5500.00"))
        dining_table_6 = Product(name="Dining Table (6 seater)", selling_price=Decimal("28000.00"), labor_cost=Decimal("7000.00"))
        dining_table_8 = Product(name="Dining Table (8 seater)", selling_price=Decimal("38000.00"), labor_cost=Decimal("7500.00"))
        ordinary_table = Product(name="Ordinary Table", selling_price=Decimal("7000.00"), labor_cost=Decimal("1200.00"))
        bed_frame = Product(name="Bed Frame", selling_price=Decimal("15000.00"), labor_cost=Decimal("1500.00"))
        door_60 = Product(name="Door (60x210)", selling_price=Decimal("3800.00"), labor_cost=Decimal("500.00"))
        door_70 = Product(name="Door (70x210)", selling_price=Decimal("3800.00"), labor_cost=Decimal("500.00"))
        door_80 = Product(name="Door (80x210)", selling_price=Decimal("3800.00"), labor_cost=Decimal("500.00"))
        door_90 = Product(name="Door (90x210)", selling_price=Decimal("3800.00"), labor_cost=Decimal("500.00"))
        high_chair = Product(name="High Chair", selling_price=Decimal("3500.00"), labor_cost=Decimal("350.00"))
        ordinary_chair = Product(name="Ordinary Chair", selling_price=Decimal("3500.00"), labor_cost=Decimal("300.00"))

        db.add_all([
            dining_table_4, dining_table_6, dining_table_8, ordinary_table,
            bed_frame, door_60, door_70, door_80, door_90,
            high_chair, ordinary_chair,
        ])

        db.flush()

        # -------------------------
        # Product Resource Requirements (exact client BOM)
        # -------------------------

        def req(product, resource, quantity):
            return ProductResourceRequirement(
                product_id=product.id,
                resource_id=resource.id,
                quantity_required=Decimal(str(quantity)),
            )

        requirements = [
            # Dining Table (4 seater)
            req(dining_table_4, wood, "45.0000"),
            req(dining_table_4, epoxy, "0.3000"),
            req(dining_table_4, nails, "0.3000"),
            req(dining_table_4, wood_glue, "0.3000"),
            req(dining_table_4, sandpaper, "4.0000"),
            req(dining_table_4, labor, "36.0000"),
            req(dining_table_4, circular_saw, "3.0000"),
            req(dining_table_4, table_planer, "2.0000"),
            req(dining_table_4, hand_planer, "1.0000"),

            # Dining Table (6 seater)
            req(dining_table_6, wood, "60.0000"),
            req(dining_table_6, epoxy, "0.4000"),
            req(dining_table_6, nails, "0.4000"),
            req(dining_table_6, wood_glue, "0.4000"),
            req(dining_table_6, sandpaper, "4.0000"),
            req(dining_table_6, labor, "36.0000"),
            req(dining_table_6, circular_saw, "3.0000"),
            req(dining_table_6, table_planer, "2.0000"),
            req(dining_table_6, hand_planer, "1.0000"),

            # Dining Table (8 seater)
            req(dining_table_8, wood, "70.0000"),
            req(dining_table_8, epoxy, "0.5000"),
            req(dining_table_8, nails, "0.5000"),
            req(dining_table_8, wood_glue, "0.5000"),
            req(dining_table_8, sandpaper, "5.0000"),
            req(dining_table_8, labor, "36.0000"),
            req(dining_table_8, circular_saw, "3.0000"),
            req(dining_table_8, table_planer, "2.0000"),
            req(dining_table_8, hand_planer, "1.0000"),

            # Ordinary Table
            req(ordinary_table, wood, "15.0000"),
            req(ordinary_table, epoxy, "0.2000"),
            req(ordinary_table, nails, "0.2000"),
            req(ordinary_table, wood_glue, "0.2000"),
            req(ordinary_table, sandpaper, "2.0000"),
            req(ordinary_table, labor, "8.0000"),
            req(ordinary_table, circular_saw, "2.0000"),
            req(ordinary_table, table_planer, "1.0000"),
            req(ordinary_table, hand_planer, "1.0000"),

            # Bed Frame
            req(bed_frame, wood, "30.0000"),
            req(bed_frame, epoxy, "0.2000"),
            req(bed_frame, nails, "0.4000"),
            req(bed_frame, wood_glue, "0.3000"),
            req(bed_frame, sandpaper, "4.0000"),
            req(bed_frame, labor, "24.0000"),
            req(bed_frame, circular_saw, "3.0000"),
            req(bed_frame, table_planer, "2.0000"),
            req(bed_frame, hand_planer, "1.0000"),

            # Door (60x210)
            req(door_60, wood, "22.0000"),
            req(door_60, epoxy, "0.2000"),
            req(door_60, nails, "0.2000"),
            req(door_60, wood_glue, "0.2000"),
            req(door_60, sandpaper, "3.0000"),
            req(door_60, doorknob, "1.0000"),
            req(door_60, labor, "8.0000"),
            req(door_60, circular_saw, "1.0000"),
            req(door_60, table_planer, "1.0000"),
            req(door_60, hand_planer, "0.5000"),

            # Door (70x210)
            req(door_70, wood, "25.0000"),
            req(door_70, epoxy, "0.2000"),
            req(door_70, nails, "0.2000"),
            req(door_70, wood_glue, "0.2000"),
            req(door_70, sandpaper, "3.0000"),
            req(door_70, doorknob, "1.0000"),
            req(door_70, labor, "8.0000"),
            req(door_70, circular_saw, "1.0000"),
            req(door_70, table_planer, "1.0000"),
            req(door_70, hand_planer, "0.5000"),

            # Door (80x210)
            req(door_80, wood, "28.0000"),
            req(door_80, epoxy, "0.2000"),
            req(door_80, nails, "0.2000"),
            req(door_80, wood_glue, "0.2000"),
            req(door_80, sandpaper, "3.0000"),
            req(door_80, doorknob, "1.0000"),
            req(door_80, labor, "8.0000"),
            req(door_80, circular_saw, "1.0000"),
            req(door_80, table_planer, "1.0000"),
            req(door_80, hand_planer, "0.5000"),

            # Door (90x210)
            req(door_90, wood, "30.0000"),
            req(door_90, epoxy, "0.2000"),
            req(door_90, nails, "0.2000"),
            req(door_90, wood_glue, "0.2000"),
            req(door_90, sandpaper, "3.0000"),
            req(door_90, doorknob, "1.0000"),
            req(door_90, labor, "8.0000"),
            req(door_90, circular_saw, "1.0000"),
            req(door_90, table_planer, "1.0000"),
            req(door_90, hand_planer, "0.5000"),

            # High Chair
            req(high_chair, wood, "8.0000"),
            req(high_chair, epoxy, "0.1000"),
            req(high_chair, nails, "0.0500"),
            req(high_chair, wood_glue, "0.1000"),
            req(high_chair, sandpaper, "2.0000"),
            req(high_chair, labor, "8.0000"),
            req(high_chair, circular_saw, "2.0000"),
            req(high_chair, table_planer, "1.0000"),
            req(high_chair, hand_planer, "1.0000"),

            # Ordinary Chair
            req(ordinary_chair, wood, "8.0000"),
            req(ordinary_chair, epoxy, "0.1000"),
            req(ordinary_chair, nails, "0.0500"),
            req(ordinary_chair, wood_glue, "0.1000"),
            req(ordinary_chair, sandpaper, "2.0000"),
            req(ordinary_chair, labor, "8.0000"),
            req(ordinary_chair, circular_saw, "2.0000"),
            req(ordinary_chair, table_planer, "1.0000"),
            req(ordinary_chair, hand_planer, "1.0000"),
        ]

        db.add_all(requirements)

        # -------------------------
        # Production Cycle
        # -------------------------

        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=7)

        cycle = ProductionCycle(
            cycle_date=start_date,
            start_date=start_date,
            end_date=end_date,
            status="OPEN",
        )

        db.add(cycle)
        db.flush()

        # -------------------------
        # Cycle Resources (client's Available Resources Per Week)
        # -------------------------
        #
        # Labor's unit_price is intentionally 0.00 and NOT used for
        # costing (see calculate_unit_profit in optimization.py) - the
        # 576-hour availability below is still the real ILP capacity
        # constraint. It cannot be left unset: CycleResource.unit_price
        # is a required column and every other resource here still
        # needs a real per-unit price for the optimizer's cost model.

        db.add_all([
            CycleResource(production_cycle=cycle, resource=wood, available_quantity=Decimal("1250.0000"), unit_price=Decimal("84.00")),
            CycleResource(production_cycle=cycle, resource=epoxy, available_quantity=Decimal("8.0000"), unit_price=Decimal("690.00")),
            CycleResource(production_cycle=cycle, resource=nails, available_quantity=Decimal("100.0000"), unit_price=Decimal("54.00")),
            CycleResource(production_cycle=cycle, resource=wood_glue, available_quantity=Decimal("12.0000"), unit_price=Decimal("79.00")),
            CycleResource(production_cycle=cycle, resource=sandpaper, available_quantity=Decimal("100.0000"), unit_price=Decimal("10.00")),
            CycleResource(production_cycle=cycle, resource=doorknob, available_quantity=Decimal("13.0000"), unit_price=Decimal("300.00")),
            CycleResource(production_cycle=cycle, resource=labor, available_quantity=Decimal("576.0000"), unit_price=Decimal("0.00")),
            CycleResource(production_cycle=cycle, resource=circular_saw, available_quantity=Decimal("336.0000"), unit_price=Decimal("31.57")),
            CycleResource(production_cycle=cycle, resource=table_planer, available_quantity=Decimal("96.0000"), unit_price=Decimal("31.57")),
            CycleResource(production_cycle=cycle, resource=hand_planer, available_quantity=Decimal("240.0000"), unit_price=Decimal("15.78")),
        ])

        db.commit()

        print("Database seed completed successfully.")
        print(f"Production cycle id: {cycle.id}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    session = SessionLocal()

    try:
        reset_demo_data(session)
        print("Demo data reset completed.")
    finally:
        session.close()

    seed_database()
