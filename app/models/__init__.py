"""Entity models registry."""

from app.models.base import TimestampMixin
from app.models.user import User
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.medicine import Medicine, MedicineBatch
from app.models.purchase import Purchase, PurchaseItem
from app.models.sale import Sale, SaleItem
from app.models.prescription import Prescription
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.models.setting import AppSetting

__all__ = [
    "TimestampMixin",
    "User",
    "Category",
    "Supplier",
    "Customer",
    "Medicine",
    "MedicineBatch",
    "Purchase",
    "PurchaseItem",
    "Sale",
    "SaleItem",
    "Prescription",
    "Notification",
    "AuditLog",
    "AppSetting",
]
