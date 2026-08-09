from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Product
from app.schemas.product import ProductCreate, ProductUpdate


def get_products(db: Session) -> list[Product]:
    statement = (
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.id)
    )

    return list(
        db.scalars(statement).all()
    )


def get_product(
    db: Session,
    product_id: int,
) -> Product | None:
    statement = select(Product).where(
        Product.id == product_id
    )

    return db.scalars(statement).first()


def create_product(
    db: Session,
    product_data: ProductCreate,
) -> Product:
    product = Product(
        name=product_data.name,
        selling_price=product_data.selling_price,
        is_active=product_data.is_active,
    )

    try:
        db.add(product)
        db.commit()
        db.refresh(product)

        return product

    except Exception:
        db.rollback()
        raise


def update_product(
    db: Session,
    product: Product,
    product_data: ProductUpdate,
) -> Product:
    update_data = product_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        db.commit()
        db.refresh(product)

        return product

    except Exception:
        db.rollback()
        raise


def delete_product(
    db: Session,
    product: Product,
) -> None:
    try:
        product.is_active = False

        db.commit()

    except Exception:
        db.rollback()
        raise