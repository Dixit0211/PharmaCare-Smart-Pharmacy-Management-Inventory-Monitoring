"""Medicine category classification model."""

from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.medicine import Medicine


class Category(Base, TimestampMixin):
    """Pharmaceutical categories (e.g., Antibiotics, Analgesics, Antacids)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    medicines: Mapped[List["Medicine"]] = relationship("Medicine", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name='{self.name}'>"
