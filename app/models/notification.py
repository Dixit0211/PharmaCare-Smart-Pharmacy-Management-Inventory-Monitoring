"""System alerts and inventory notifications model."""

from typing import Optional
from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import TimestampMixin


class Notification(Base, TimestampMixin):
    """System alerts for low stock, expiring medicines, and key events."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(50), default="info", nullable=False)  # expiry, low_stock, purchase, sale, system
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)  # info, warning, critical
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # E.g. medicine_id or batch_id

    def __repr__(self) -> str:
        return f"<Notification id={self.id} type='{self.type}' title='{self.title}' is_read={self.is_read}>"
