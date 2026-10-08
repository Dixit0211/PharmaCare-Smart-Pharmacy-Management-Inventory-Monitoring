"""Doctor prescription tracking model."""

from datetime import date
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.sale import Sale


class Prescription(Base, TimestampMixin):
    """Medical prescriptions required for Schedule H/X medicines."""

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doctor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    doctor_reg_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    patient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    patient_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patient_gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    prescription_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Path to uploaded scan / image

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="prescriptions")
    sales: Mapped[List["Sale"]] = relationship("Sale", back_populates="prescription")

    def __repr__(self) -> str:
        return f"<Prescription id={self.id} doctor='{self.doctor_name}' patient='{self.patient_name}'>"
