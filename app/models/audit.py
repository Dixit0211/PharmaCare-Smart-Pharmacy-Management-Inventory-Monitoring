"""Security and compliance audit trail log model."""

from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base, TimestampMixin):
    """Immutable audit trail of actions taken in the pharmacy system."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str] = mapped_column(String(50), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, EXPORT, BACKUP
    module: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # MEDICINES, BILLING, INVENTORY, USERS, etc.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} user='{self.username}' action='{self.action}' module='{self.module}'>"
