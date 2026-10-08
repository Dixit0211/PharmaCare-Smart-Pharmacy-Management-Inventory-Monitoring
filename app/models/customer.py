"""Customer / Patient entity model."""

from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.sale import Sale
    from app.models.prescription import Prescription


class Customer(Base, TimestampMixin):
    """Customer records for billing, prescription tracking, and sales history."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    sales: Mapped[List["Sale"]] = relationship("Sale", back_populates="customer")
    prescriptions: Mapped[List["Prescription"]] = relationship("Prescription", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name='{self.name}' phone='{self.phone}'>"
