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
    db = SessionLocal()

    try:
        # -------------------------
        # Resources
        # -------------------------

        wood = Resource(name="Wood", resource_type="material", unit="kg")
        epoxy = Resource(name="Epoxy", resource_type="material", unit="kg")
        nails = Resource(name="Nails", resource_type="material", unit="kg")
        wood_glue = Resource(name="Wood Glue", resource_type="material", unit="liter")
        sandpaper = Resource(name="Sandpaper", resource_type="material", unit="pcs")
        doorknob = Resource(name="Doorknob", resource_type="material", unit="pcs")
        labor = Resource(name="Labor", resource_type="labor", unit="hours")
        circular_saw = Resource(name="Circular Saw", resource_type="machine", unit="hours")
        table_planer = Resource(name="Table Planer", resource_type="machine", unit="hours")
        hand_planer = Resource(name="Hand Planer", resource_type="machine", unit="hours")

        db.add_all([
            wood, epoxy, nails, wood_glue, sandpaper, doorknob,
            labor, circular_saw, table_planer, hand_planer,
        ])

        # -------------------------
        # Products
        # -------------------------

        dining_table = Product(name="Dining Table", selling_price=Decimal("12500.00"))
        dining_table_6 = Product(name="6-Seater Dining Table", selling_price=Decimal("18500.00"))
        dining_table_8 = Product(name="8-Seater Dining Table", selling_price=Decimal("24000.00"))
        dining_chair = Product(name="Dining Chair", selling_price=Decimal("3500.00"))
        high_chair = Product(name="High Chair", selling_price=Decimal("4500.00"))
        bed_frame = Product(name="Bed Frame", selling_price=Decimal("15000.00"))
        wardrobe = Product(name="Wardrobe", selling_price=Decimal("22000.00"))
        side_table = Product(name="Side Table", selling_price=Decimal("4500.00"))
        wooden_door = Product(name="Wooden Door", selling_price=Decimal("8500.00"))
        office_desk = Product(name="Office Desk", selling_price=Decimal("9500.00"))

        db.add_all([
            dining_table, dining_table_6, dining_table_8, dining_chair,
            high_chair, bed_frame, wardrobe, side_table, wooden_door,
            office_desk,
        ])

        db.flush()

        # -------------------------
        # Product Resource Requirements
        # -------------------------

        def req(product, resource, quantity):
            return ProductResourceRequirement(
                product_id=product.id,
                resource_id=resource.id,
                quantity_required=Decimal(str(quantity)),
            )

        requirements = [
            # Dining Table
            req(dining_table, wood, "12.0000"),
            req(dining_table, epoxy, "0.5000"),
            req(dining_table, nails, "0.1500"),
            req(dining_table, wood_glue, "0.3000"),
            req(dining_table, sandpaper, "2.0000"),
            req(dining_table, labor, "8.0000"),
            req(dining_table, circular_saw, "1.5000"),
            req(dining_table, table_planer, "0.5000"),

            # 6-Seater Dining Table
            req(dining_table_6, wood, "18.0000"),
            req(dining_table_6, epoxy, "0.7500"),
            req(dining_table_6, nails, "0.2000"),
            req(dining_table_6, wood_glue, "0.4500"),
            req(dining_table_6, sandpaper, "3.0000"),
            req(dining_table_6, labor, "12.0000"),
            req(dining_table_6, circular_saw, "2.0000"),
            req(dining_table_6, table_planer, "0.8000"),

            # 8-Seater Dining Table
            req(dining_table_8, wood, "24.0000"),
            req(dining_table_8, epoxy, "1.0000"),
            req(dining_table_8, nails, "0.2500"),
            req(dining_table_8, wood_glue, "0.6000"),
            req(dining_table_8, sandpaper, "4.0000"),
            req(dining_table_8, labor, "16.0000"),
            req(dining_table_8, circular_saw, "2.5000"),
            req(dining_table_8, table_planer, "1.0000"),

            # Dining Chair
            req(dining_chair, wood, "5.0000"),
            req(dining_chair, nails, "0.0800"),
            req(dining_chair, wood_glue, "0.1500"),
            req(dining_chair, sandpaper, "1.0000"),
            req(dining_chair, labor, "3.0000"),
            req(dining_chair, circular_saw, "0.5000"),
            req(dining_chair, hand_planer, "0.3000"),

            # High Chair
            req(high_chair, wood, "4.0000"),
            req(high_chair, nails, "0.0600"),
            req(high_chair, wood_glue, "0.1000"),
            req(high_chair, sandpaper, "1.0000"),
            req(high_chair, labor, "3.5000"),
            req(high_chair, circular_saw, "0.4000"),
            req(high_chair, hand_planer, "0.3000"),

            # Bed Frame
            req(bed_frame, wood, "25.0000"),
            req(bed_frame, nails, "0.2500"),
            req(bed_frame, wood_glue, "0.5000"),
            req(bed_frame, sandpaper, "3.0000"),
            req(bed_frame, labor, "10.0000"),
            req(bed_frame, circular_saw, "2.0000"),
            req(bed_frame, table_planer, "1.0000"),

            # Wardrobe
            req(wardrobe, wood, "40.0000"),
            req(wardrobe, nails, "0.3000"),
            req(wardrobe, wood_glue, "0.6000"),
            req(wardrobe, sandpaper, "5.0000"),
            req(wardrobe, doorknob, "2.0000"),
            req(wardrobe, labor, "18.0000"),
            req(wardrobe, circular_saw, "3.0000"),
            req(wardrobe, table_planer, "1.5000"),

            # Side Table
            req(side_table, wood, "6.0000"),
            req(side_table, nails, "0.1000"),
            req(side_table, wood_glue, "0.1500"),
            req(side_table, sandpaper, "1.0000"),
            req(side_table, labor, "3.0000"),
            req(side_table, circular_saw, "0.5000"),
            req(side_table, hand_planer, "0.3000"),

            # Wooden Door
            req(wooden_door, wood, "15.0000"),
            req(wooden_door, nails, "0.2000"),
            req(wooden_door, wood_glue, "0.3000"),
            req(wooden_door, sandpaper, "2.0000"),
            req(wooden_door, doorknob, "1.0000"),
            req(wooden_door, labor, "6.0000"),
            req(wooden_door, circular_saw, "1.0000"),
            req(wooden_door, table_planer, "0.5000"),

            # Office Desk
            req(office_desk, wood, "20.0000"),
            req(office_desk, epoxy, "0.4000"),
            req(office_desk, nails, "0.2000"),
            req(office_desk, wood_glue, "0.4000"),
            req(office_desk, sandpaper, "3.0000"),
            req(office_desk, labor, "9.0000"),
            req(office_desk, circular_saw, "1.5000"),
            req(office_desk, table_planer, "0.7000"),
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
        # Cycle Resources (availability + unit price for this cycle)
        # -------------------------

        db.add_all([
            CycleResource(production_cycle=cycle, resource=wood, available_quantity=Decimal("1250.0000"), unit_price=Decimal("84.0000")),
            CycleResource(production_cycle=cycle, resource=epoxy, available_quantity=Decimal("25.0000"), unit_price=Decimal("650.0000")),
            CycleResource(production_cycle=cycle, resource=nails, available_quantity=Decimal("100.0000"), unit_price=Decimal("120.0000")),
            CycleResource(production_cycle=cycle, resource=wood_glue, available_quantity=Decimal("50.0000"), unit_price=Decimal("79.0000")),
            CycleResource(production_cycle=cycle, resource=sandpaper, available_quantity=Decimal("500.0000"), unit_price=Decimal("10.0000")),
            CycleResource(production_cycle=cycle, resource=doorknob, available_quantity=Decimal("100.0000"), unit_price=Decimal("300.0000")),
            CycleResource(production_cycle=cycle, resource=labor, available_quantity=Decimal("576.0000"), unit_price=Decimal("150.0000")),
            CycleResource(production_cycle=cycle, resource=circular_saw, available_quantity=Decimal("200.0000"), unit_price=Decimal("80.0000")),
            CycleResource(production_cycle=cycle, resource=table_planer, available_quantity=Decimal("150.0000"), unit_price=Decimal("100.0000")),
            CycleResource(production_cycle=cycle, resource=hand_planer, available_quantity=Decimal("150.0000"), unit_price=Decimal("60.0000")),
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
