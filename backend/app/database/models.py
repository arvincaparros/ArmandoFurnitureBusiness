from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    selling_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    resource_requirements: Mapped[
        list["ProductResourceRequirement"]
    ] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

    production_allocations: Mapped[
        list["ProductionAllocation"]
    ] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

    sales_transactions: Mapped[
        list["SalesTransaction"]
    ] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

    forecast_results: Mapped[
        list["ForecastResult"]
    ] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    product_requirements: Mapped[
        list["ProductResourceRequirement"]
    ] = relationship(
        back_populates="resource",
        cascade="all, delete-orphan",
    )

    cycle_resources: Mapped[
        list["CycleResource"]
    ] = relationship(
        back_populates="resource",
        cascade="all, delete-orphan",
    )

class ProductResourceRequirement(Base):
    __tablename__ = "product_resource_requirements"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    quantity_required: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    product: Mapped["Product"] = relationship(
        back_populates="resource_requirements",
    )

    resource: Mapped["Resource"] = relationship(
        back_populates="product_requirements",
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "resource_id",
            name="uq_product_resource_requirement",
        ),
    )

class ProductionCycle(Base):
    __tablename__ = "production_cycles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    cycle_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="OPEN",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    cycle_resources: Mapped[
        list["CycleResource"]
    ] = relationship(
        back_populates="production_cycle",
        cascade="all, delete-orphan",
    )

    production_allocations: Mapped[
        list["ProductionAllocation"]
    ] = relationship(
        back_populates="production_cycle",
        cascade="all, delete-orphan",
    )

    optimization_runs: Mapped[
        list["OptimizationRun"]
    ] = relationship(
        back_populates="production_cycle",
        cascade="all, delete-orphan",
    )

class CycleResource(Base):
    __tablename__ = "cycle_resources"

    __table_args__ = (
        UniqueConstraint(
            "production_cycle_id",
            "resource_id",
            name="uq_cycle_resource",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    production_cycle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "production_cycles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[int] = mapped_column(
        ForeignKey(
            "resources.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    available_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    production_cycle: Mapped["ProductionCycle"] = relationship(
        back_populates="cycle_resources",
    )

    resource: Mapped["Resource"] = relationship(
        back_populates="cycle_resources",
    )

class ProductionAllocation(Base):
    __tablename__ = "production_allocations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    production_cycle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "production_cycles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    production_cycle: Mapped["ProductionCycle"] = relationship(
        back_populates="production_allocations",
    )

    product: Mapped["Product"] = relationship(
        back_populates="production_allocations",
    )

    __table_args__ = (
        UniqueConstraint(
            "production_cycle_id",
            "product_id",
            name="uq_production_allocation",
        ),
    )

class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    production_cycle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "production_cycles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    objective_value: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    total_profit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    production_cycle: Mapped["ProductionCycle"] = relationship(
        back_populates="optimization_runs",
    )

    results: Mapped[
        list["OptimizationResult"]
    ] = relationship(
        back_populates="optimization_run",
        cascade="all, delete-orphan",
    )

class OptimizationResult(Base):
    __tablename__ = "optimization_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    optimization_run_id: Mapped[int] = mapped_column(
        ForeignKey(
            "optimization_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    recommended_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    unit_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    total_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    optimization_run: Mapped["OptimizationRun"] = relationship(
        back_populates="results",
    )

    product: Mapped["Product"] = relationship()

class SalesTransaction(Base):
    __tablename__ = "sales_transactions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    transaction_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: f"TRX-{uuid4().hex[:12].upper()}",
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # Quantity produced during the production process
    quantity_produced: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    # Quantity sold
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    total_sales: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # Total production cost associated with this transaction
    production_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    unit_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    total_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    product: Mapped["Product"] = relationship()

class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    forecast_period: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    results: Mapped[
        list["ForecastResult"]
    ] = relationship(
        back_populates="forecast_run",
        cascade="all, delete-orphan",
    )

class ForecastResult(Base):
    __tablename__ = "forecast_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    forecast_run_id: Mapped[int] = mapped_column(
        ForeignKey(
            "forecast_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    historical_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    forecast_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    trend: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    confidence_level: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    forecast_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    forecast_run: Mapped["ForecastRun"] = relationship(
        back_populates="results",
    )

    product: Mapped["Product"] = relationship(
        back_populates="forecast_results",
    )

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    reset_tokens: Mapped[
        list["PasswordResetToken"]
    ] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Only a hash of the token is stored (same principle as
    # password_hash) - if this table were ever exposed/leaked, the
    # hashes alone can't be used to reset anyone's password.
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # NULL = unused/valid (subject to expires_at). Set once the token
    # is redeemed so it can never be used a second time.
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    user: Mapped["User"] = relationship(
        back_populates="reset_tokens",
    )


class ResourceUtilizationRun(Base):
    """
    One immutable snapshot of resource utilization, created exactly
    once - when "Apply to Production" successfully completes (see
    app/services/optimization.py::apply_optimization). Mirrors
    OptimizationRun/OptimizationResult's parent-child shape above.
    Never created by generating an optimization preview, and never
    updated afterward - its ResourceUtilizationHistoryItem rows are
    the historical record, independent of whatever Resource/
    CycleResource data says today.
    """

    __tablename__ = "resource_utilization_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Same "friendly sequential id" convention as SalesTransaction's
    # transaction_number (see app/services/transaction.py::
    # generate_transaction_number) - the service layer generates and
    # passes "UT-0001"-style values; this default is only a fallback
    # for any row created without going through that helper.
    utilization_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: f"UT-{uuid4().hex[:8].upper()}",
    )

    production_cycle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "production_cycles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    production_cycle: Mapped["ProductionCycle"] = relationship()

    items: Mapped[
        list["ResourceUtilizationHistoryItem"]
    ] = relationship(
        back_populates="utilization_run",
        cascade="all, delete-orphan",
    )


class ResourceUtilizationHistoryItem(Base):
    """
    One resource's snapshotted utilization figures within a single
    ResourceUtilizationRun. resource_id is kept (ondelete=SET NULL,
    nullable) for referential integrity/lookups, but every field a
    history view actually needs to render is duplicated directly onto
    this row at creation time - resource_name/resource_type/unit
    alongside the calculated quantities/rate/status - so the row stays
    fully displayable even if the Resource it pointed to is later
    renamed, deactivated, or (hypothetically) removed. Never
    recalculated from current Resource/CycleResource/
    ProductionAllocation data after creation.
    """

    __tablename__ = "resource_utilization_history_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    utilization_run_id: Mapped[int] = mapped_column(
        ForeignKey(
            "resource_utilization_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "resources.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Snapshotted at creation time - see class docstring.
    resource_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    available_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    consumed_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    remaining_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    utilization_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )

    # "normal" | "high" | "at_risk" | "bottleneck" - the exact value
    # classify_utilization_status() returned at snapshot time (see
    # app/services/resource_utilization.py). Never reclassified later
    # even if the shared thresholds change.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    utilization_run: Mapped["ResourceUtilizationRun"] = relationship(
        back_populates="items",
    )

    resource: Mapped["Resource | None"] = relationship()