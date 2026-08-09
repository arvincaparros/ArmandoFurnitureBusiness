from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database.connection import SessionLocal
from app.database.models import (
    CycleResource,
    Product,
    ProductResourceRequirement,
    ProductionCycle,
    Resource,
)


def seed_database() -> None:
    db = SessionLocal()

    try:
        # Prevent duplicate seed data
        if db.query(Product).first():
            print("Database already contains product data. Skipping seed.")
            return

        # -------------------------
        # Resources
        # -------------------------

        wood = Resource(
            name="Wood",
            resource_type="material",
            unit="kg",
        )

        epoxy = Resource(
            name="Epoxy",
            resource_type="material",
            unit="kg",
        )

        nails = Resource(
            name="Nails",
            resource_type="material",
            unit="kg",
        )

        labor = Resource(
            name="Labor",
            resource_type="labor",
            unit="hours",
        )

        db.add_all([
            wood,
            epoxy,
            nails,
            labor,
        ])

        # -------------------------
        # Products
        # -------------------------

        dining_table = Product(
            name="Dining Table",
            selling_price=Decimal("12500.00"),
        )

        chair = Product(
            name="Chair",
            selling_price=Decimal("3500.00"),
        )

        bed_frame = Product(
            name="Bed Frame",
            selling_price=Decimal("15000.00"),
        )

        db.add_all([
            dining_table,
            chair,
            bed_frame,
        ])

        db.flush()

        # -------------------------
        # Product Resource Requirements
        # -------------------------

        db.add_all([
            ProductResourceRequirement(
                product=dining_table,
                resource=wood,
                quantity_required=Decimal("45.0000"),
            ),
            ProductResourceRequirement(
                product=dining_table,
                resource=epoxy,
                quantity_required=Decimal("0.3000"),
            ),
            ProductResourceRequirement(
                product=dining_table,
                resource=nails,
                quantity_required=Decimal("0.3000"),
            ),
            ProductResourceRequirement(
                product=dining_table,
                resource=labor,
                quantity_required=Decimal("36.0000"),
            ),

            ProductResourceRequirement(
                product=chair,
                resource=wood,
                quantity_required=Decimal("12.0000"),
            ),
            ProductResourceRequirement(
                product=chair,
                resource=nails,
                quantity_required=Decimal("0.1500"),
            ),
            ProductResourceRequirement(
                product=chair,
                resource=labor,
                quantity_required=Decimal("8.0000"),
            ),

            ProductResourceRequirement(
                product=bed_frame,
                resource=wood,
                quantity_required=Decimal("55.0000"),
            ),
            ProductResourceRequirement(
                product=bed_frame,
                resource=nails,
                quantity_required=Decimal("0.4000"),
            ),
            ProductResourceRequirement(
                product=bed_frame,
                resource=labor,
                quantity_required=Decimal("40.0000"),
            ),
        ])

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
        # Cycle Resources
        # -------------------------

        db.add_all([
            CycleResource(
                production_cycle=cycle,
                resource=wood,
                available_quantity=Decimal("1250.0000"),
                unit_price=Decimal("84.0000"),
            ),
            CycleResource(
                production_cycle=cycle,
                resource=epoxy,
                available_quantity=Decimal("8.0000"),
                unit_price=Decimal("650.0000"),
            ),
            CycleResource(
                production_cycle=cycle,
                resource=nails,
                available_quantity=Decimal("100.0000"),
                unit_price=Decimal("120.0000"),
            ),
            CycleResource(
                production_cycle=cycle,
                resource=labor,
                available_quantity=Decimal("576.0000"),
                unit_price=Decimal("150.0000"),
            ),
        ])

        db.commit()

        print("Database seed completed successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()