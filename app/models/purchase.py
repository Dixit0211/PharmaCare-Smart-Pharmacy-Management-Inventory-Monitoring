"""Purchase orders and incoming stock items."""

from datetime import date
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.supplier import Supplier
    from app.models.medicine import Medicine


class Purchase(Base, TimestampMixin):
    """Inward procurement invoice from pharmaceutical suppliers."""

    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    invoice_no: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="received", nullable=False)  # received | pending | cancelled
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="purchases")
    items: Mapped[List["PurchaseItem"]] = relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Purchase id={self.id} invoice='{self.invoice_no}' total={self.total_amount}>"


class PurchaseItem(Base, TimestampMixin):
    """Line item within a purchase invoice."""

    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    purchase: Mapped["Purchase"] = relationship("Purchase", back_populates="items")
    medicine: Mapped["Medicine"] = relationship("Medicine", back_populates="purchase_items")

    def __repr__(self) -> str:
        return f"<PurchaseItem id={self.id} med_id={self.medicine_id} batch='{self.batch_no}' qty={self.quantity}>"
