"""
The one fixed, historical 11-product catalog behind every Week
Reference Verification comparison - verified in the Week 1-8
reconstruction investigation to reproduce the "weekly data
references.xlsx" workbook's allocation and profit exactly (within
~P0.3-0.4 of Excel's own rounding) for all 8 weeks when combined with
that week's own resource availability and NO forecast ceiling.

Deliberately independent of app.database.models: this catalog is
never read from or written to the live products/resources/
product_resource_requirements tables (Product Data Management owns
those) - it exists only to feed the real solve_optimization().

The Hand Planer requirement on the four doors/High Chair/Ordinary
Chair (2.0000, not 3.0000) and Bed Frame's Wood Glue requirement
(0.3000, not the live catalog's separately-approved-current 1.3000)
are the historically-verified values, not necessarily what Product
Data Management shows today - see the Week 1-8 reconstruction
investigation for how each was confirmed (reconciling all 10
per-resource consumption figures and total profit for every one of
the 8 weeks, not just Week 1).
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CatalogResource:
    id: int
    name: str
    unit: str
    resource_type: str
    is_active: bool = True


@dataclass
class CatalogProduct:
    id: int
    name: str
    selling_price: Decimal
    labor_cost: Decimal
    minimum_demand: Decimal
    is_active: bool = True


@dataclass
class CatalogRequirement:
    product_id: int
    resource_id: int
    quantity_required: Decimal


CATALOG_RESOURCES: dict[str, CatalogResource] = {
    "wood": CatalogResource(1, "Wood", "bf", "material"),
    "sandpaper": CatalogResource(2, "Sandpaper", "pcs", "material"),
    "nails": CatalogResource(3, "Nails", "kg", "material"),
    "wood_glue": CatalogResource(4, "Wood Glue", "L", "material"),
    "epoxy": CatalogResource(5, "Epoxy", "L", "material"),
    "labor": CatalogResource(6, "Labor", "hrs", "labor"),
    "circular_saw": CatalogResource(7, "Circular Saw", "hrs", "machine"),
    "hand_planer": CatalogResource(8, "Hand Planer", "hrs", "machine"),
    "table_planer": CatalogResource(9, "Table Planer", "hrs", "machine"),
    "doorknob": CatalogResource(10, "Doorknob & Hinge", "set", "material"),
}

# Unit prices never varied across any of the 8 weeks in the workbook.
CATALOG_RESOURCE_UNIT_PRICES: dict[str, Decimal] = {
    "wood": Decimal("84.00"), "epoxy": Decimal("690.00"),
    "nails": Decimal("54.00"), "wood_glue": Decimal("79.00"),
    "labor": Decimal("0.00"), "circular_saw": Decimal("31.57"),
    "sandpaper": Decimal("10.00"), "table_planer": Decimal("31.57"),
    "hand_planer": Decimal("15.78"), "doorknob": Decimal("300.00"),
}

CATALOG_PRODUCTS: list[CatalogProduct] = [
    CatalogProduct(1, "Dining table (4 seater)", Decimal("18000.00"), Decimal("5500.00"), Decimal("1")),
    CatalogProduct(2, "Dining table (6 seater)", Decimal("28000.00"), Decimal("7000.00"), Decimal("1")),
    CatalogProduct(3, "Dining table (8 seater)", Decimal("38000.00"), Decimal("10000.00"), Decimal("0")),
    CatalogProduct(4, "Ordinary table", Decimal("7000.00"), Decimal("1200.00"), Decimal("3")),
    CatalogProduct(5, "Bed frame", Decimal("15000.00"), Decimal("1500.00"), Decimal("2")),
    CatalogProduct(6, "Door (60x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("5")),
    CatalogProduct(7, "Door (70x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("5")),
    CatalogProduct(8, "Door (80x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("4")),
    CatalogProduct(9, "Door (90x210)", Decimal("3800.00"), Decimal("500.00"), Decimal("4")),
    CatalogProduct(10, "High chair", Decimal("3500.00"), Decimal("350.00"), Decimal("2")),
    CatalogProduct(11, "Ordinary chair", Decimal("3500.00"), Decimal("300.00"), Decimal("3")),
]

# Keys match week_references.json's "product_order" 1-for-1 (index 0 -> id 1, etc.)
CATALOG_PRODUCT_KEYS: list[str] = [
    "dining_table_4", "dining_table_6", "dining_table_8", "ordinary_table",
    "bed_frame", "door_60", "door_70", "door_80", "door_90",
    "high_chair", "ordinary_chair",
]

_BOM: dict[int, dict[str, str]] = {
    1: {"wood": "50.0000", "epoxy": "0.6000", "nails": "0.5000", "wood_glue": "0.6000", "circular_saw": "15.0000", "sandpaper": "10.0000", "table_planer": "10.0000", "hand_planer": "10.0000", "labor": "40.0000"},
    2: {"wood": "75.0000", "epoxy": "1.0000", "nails": "0.5000", "wood_glue": "1.0000", "circular_saw": "20.0000", "sandpaper": "16.0000", "table_planer": "15.0000", "hand_planer": "15.0000", "labor": "60.0000"},
    3: {"wood": "100.0000", "epoxy": "1.5000", "nails": "1.0000", "wood_glue": "1.5000", "circular_saw": "30.0000", "sandpaper": "22.0000", "table_planer": "20.0000", "hand_planer": "20.0000", "labor": "80.0000"},
    4: {"wood": "15.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "2.0000", "table_planer": "2.0000", "hand_planer": "2.0000", "labor": "10.0000"},
    5: {"wood": "30.0000", "epoxy": "0.2000", "nails": "0.4000", "wood_glue": "0.3000", "circular_saw": "10.0000", "sandpaper": "4.0000", "table_planer": "10.0000", "hand_planer": "10.0000", "labor": "40.0000"},
    6: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    7: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    8: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    9: {"wood": "25.0000", "epoxy": "0.2000", "nails": "0.2000", "wood_glue": "0.2000", "circular_saw": "2.0000", "sandpaper": "3.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "doorknob": "1.0000", "labor": "8.0000"},
    10: {"wood": "8.0000", "epoxy": "0.1000", "nails": "0.0500", "wood_glue": "0.1000", "circular_saw": "2.0000", "sandpaper": "2.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "labor": "8.0000"},
    11: {"wood": "8.0000", "epoxy": "0.1000", "nails": "0.0500", "wood_glue": "0.1000", "circular_saw": "2.0000", "sandpaper": "2.0000", "table_planer": "1.0000", "hand_planer": "2.0000", "labor": "8.0000"},
}

CATALOG_REQUIREMENTS: list[tuple[CatalogRequirement, CatalogResource]] = [
    (
        CatalogRequirement(product_id, CATALOG_RESOURCES[resource_key].id, Decimal(quantity)),
        CATALOG_RESOURCES[resource_key],
    )
    for product_id, bom in _BOM.items()
    for resource_key, quantity in bom.items()
]
