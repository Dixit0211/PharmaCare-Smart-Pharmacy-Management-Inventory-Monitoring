"""Medicine catalog and batch inventory tracking models."""

from datetime import date
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    Date,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.purchase import PurchaseItem
    from app.models.sale import SaleItem


class Medicine(Base, TimestampMixin):
    """Medicine master record."""

    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    generic_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    dosage_form: Mapped[str] = mapped_column(String(50), default="Tablet", nullable=False)  # Tablet, Capsule, Syrup, etc.
    strength: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 500mg, 10mg
    selling_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    min_stock: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    prescription_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active | inactive

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="medicines")
    batches: Mapped[List["MedicineBatch"]] = relationship(
        "MedicineBatch",
        back_populates="medicine",
        cascade="all, delete-orphan",
        order_by="MedicineBatch.expiry_date.asc()",
    )
    purchase_items: Mapped[List["PurchaseItem"]] = relationship("PurchaseItem", back_populates="medicine")
    sale_items: Mapped[List["SaleItem"]] = relationship("SaleItem", back_populates="medicine")

    def __repr__(self) -> str:
        return f"<Medicine id={self.id} name='{self.name}' strength='{self.strength}'>"


class MedicineBatch(Base, TimestampMixin):
    """Batch-level physical inventory with explicit expiry tracking."""

    __tablename__ = "medicine_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    medicine: Mapped["Medicine"] = relationship("Medicine", back_populates="batches")
    sale_items: Mapped[List["SaleItem"]] = relationship("SaleItem", back_populates="batch")

    __table_args__ = (
        UniqueConstraint("medicine_id", "batch_no", name="uq_medicine_batch"),
        Index("ix_batch_expiry_med", "medicine_id", "expiry_date"),
    )

    def __repr__(self) -> str:
        return f"<MedicineBatch id={self.id} batch_no='{self.batch_no}' qty={self.quantity} exp={self.expiry_date}>"
