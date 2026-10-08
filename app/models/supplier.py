"""Supplier / Distributor entity model."""

from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.purchase import Purchase


class Supplier(Base, TimestampMixin):
    """Pharmaceutical wholesale distributors and suppliers."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    contact_person: Mapped[str] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    gst_number: Mapped[str] = mapped_column(String(30), nullable=True)

    # Relationships
    purchases: Mapped[List["Purchase"]] = relationship("Purchase", back_populates="supplier")

    def __repr__(self) -> str:
        return f"<Supplier id={self.id} name='{self.name}'>"
