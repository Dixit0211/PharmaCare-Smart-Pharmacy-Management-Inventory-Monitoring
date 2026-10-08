"""Sales invoices and dispensed batch items."""

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.prescription import Prescription
    from app.models.user import User
    from app.models.medicine import Medicine, MedicineBatch


class Sale(Base, TimestampMixin):
    """Outward retail/dispensing sales invoice."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_no: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    prescription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )  # Pharmacist/Cashier who billed
    payment_method: Mapped[str] = mapped_column(String(30), default="Cash", nullable=False)  # Cash, UPI, Card, Other
    subtotal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tax: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sale_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="sales")
    prescription: Mapped[Optional["Prescription"]] = relationship("Prescription", back_populates="sales")
    pharmacist_user: Mapped["User"] = relationship("User", back_populates="sales")
    items: Mapped[List["SaleItem"]] = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Sale id={self.id} invoice='{self.invoice_no}' total={self.total_amount}>"


class SaleItem(Base, TimestampMixin):
    """Line item representing medicine batch dispensed in a sale."""

    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("medicine_batches.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)  # Selling price at time of sale
    purchase_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # For accurate historical profit
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")
    medicine: Mapped["Medicine"] = relationship("Medicine", back_populates="sale_items")
    batch: Mapped["MedicineBatch"] = relationship("MedicineBatch", back_populates="sale_items")

    def __repr__(self) -> str:
        return f"<SaleItem id={self.id} med_id={self.medicine_id} batch_id={self.batch_id} qty={self.quantity}>"
