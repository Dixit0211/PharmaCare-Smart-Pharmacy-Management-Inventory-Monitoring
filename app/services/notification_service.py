"""System alerts and notification service."""

from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_, or_, desc
from app.core.database import get_db
from app.core.exceptions import ValidationError, NotFoundException
from app.models.notification import Notification
from app.models.medicine import Medicine, MedicineBatch
from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Manages automated inventory alerts, system notices, and broadcast messages."""

    @staticmethod
    def sync_inventory_alerts() -> int:
        """
        Scan active inventory and automatically generate unread notifications
        for near-expiry batches, expired stock, and low stock thresholds.
        Avoids spam by skipping duplicates if an unread notification already exists
        for the same reference ID and alert type.
        """
        today = date.today()
        near_expiry_date = today + timedelta(days=30)
        created_count = 0

        with get_db() as session:
            # 1. Check for Expired Batches (Critical)
            expired_batches = session.execute(
                select(MedicineBatch, Medicine.name, Medicine.strength)
                .join(Medicine, MedicineBatch.medicine_id == Medicine.id)
                .where(
                    and_(
                        MedicineBatch.expiry_date < today,
                        MedicineBatch.quantity > 0,
                    )
                )
            ).all()

            for b, med_name, strength in expired_batches:
                # Check if unread notification already exists
                exists = session.scalar(
                    select(func.count(Notification.id)).where(
                        and_(
                            Notification.type == "expiry",
                            Notification.reference_id == b.id,
                            Notification.is_read == False,
                        )
                    )
                )
                if not exists:
                    notif = Notification(
                        type="expiry",
                        severity="critical",
                        title=f"Quarantined: Expired Batch {b.batch_no}",
                        message=f"{med_name} ({strength}) batch #{b.batch_no} expired on {b.expiry_date.strftime('%d %b %Y')}. {b.quantity} units quarantined.",
                        reference_id=b.id,
                        is_read=False,
                    )
                    session.add(notif)
                    created_count += 1

            # 2. Check for Near-Expiry Batches (Warning / Critical)
            near_batches = session.execute(
                select(MedicineBatch, Medicine.name, Medicine.strength)
                .join(Medicine, MedicineBatch.medicine_id == Medicine.id)
                .where(
                    and_(
                        MedicineBatch.expiry_date >= today,
                        MedicineBatch.expiry_date <= near_expiry_date,
                        MedicineBatch.quantity > 0,
                    )
                )
            ).all()

            for b, med_name, strength in near_batches:
                days_left = (b.expiry_date - today).days
                exists = session.scalar(
                    select(func.count(Notification.id)).where(
                        and_(
                            Notification.type == "expiry",
                            Notification.reference_id == b.id,
                            Notification.is_read == False,
                        )
                    )
                )
                if not exists:
                    severity = "critical" if days_left <= 15 else "warning"
                    notif = Notification(
                        type="expiry",
                        severity=severity,
                        title=f"Near Expiry: {med_name} ({days_left}d left)",
                        message=f"Batch #{b.batch_no} ({b.quantity} units) expires on {b.expiry_date.strftime('%d %b %Y')}. Prioritize via FEFO.",
                        reference_id=b.id,
                        is_read=False,
                    )
                    session.add(notif)
                    created_count += 1

            # 3. Check for Low Stock / Out of Stock (Warning)
            med_stock_rows = session.execute(
                select(
                    Medicine.id,
                    Medicine.name,
                    Medicine.strength,
                    Medicine.min_stock,
                    func.coalesce(func.sum(MedicineBatch.quantity), 0).label("stock"),
                )
                .outerjoin(
                    MedicineBatch,
                    and_(
                        Medicine.id == MedicineBatch.medicine_id,
                        MedicineBatch.expiry_date >= today,
                    ),
                )
                .group_by(Medicine.id, Medicine.name, Medicine.strength, Medicine.min_stock)
                .having(func.coalesce(func.sum(MedicineBatch.quantity), 0) <= Medicine.min_stock)
            ).all()

            for r in med_stock_rows:
                exists = session.scalar(
                    select(func.count(Notification.id)).where(
                        and_(
                            Notification.type == "low_stock",
                            Notification.reference_id == r.id,
                            Notification.is_read == False,
                        )
                    )
                )
                if not exists:
                    stk = int(r.stock)
                    severity = "critical" if stk == 0 else "warning"
                    state_label = "OUT OF STOCK" if stk == 0 else "LOW STOCK"
                    notif = Notification(
                        type="low_stock",
                        severity=severity,
                        title=f"{state_label}: {r.name} ({r.strength})",
                        message=f"Current available stock is {stk} units (Safety threshold: {r.min_stock}). Place reorder with supplier.",
                        reference_id=r.id,
                        is_read=False,
                    )
                    session.add(notif)
                    created_count += 1

            if created_count > 0:
                session.commit()
                logger.info(f"Synchronized inventory alerts: created {created_count} new notifications.")

        return created_count

    @staticmethod
    def get_unread_count() -> int:
        """Get the count of unread notifications for sidebar badge."""
        with get_db() as session:
            return session.scalar(
                select(func.count(Notification.id)).where(Notification.is_read == False)
            ) or 0

    @staticmethod
    def get_notifications(
        is_read: Optional[bool] = None,
        severity: Optional[str] = None,
        notif_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch system notifications with optional status and severity filtering."""
        with get_db() as session:
            stmt = select(Notification)

            if is_read is not None:
                stmt = stmt.where(Notification.is_read == is_read)
            if severity:
                stmt = stmt.where(Notification.severity == severity)
            if notif_type:
                stmt = stmt.where(Notification.type == notif_type)

            stmt = stmt.order_by(Notification.is_read.asc(), Notification.created_at.desc()).limit(limit)
            rows = session.scalars(stmt).all()

            return [
                {
                    "id": n.id,
                    "type": n.type,
                    "severity": n.severity,
                    "title": n.title,
                    "message": n.message,
                    "is_read": n.is_read,
                    "reference_id": n.reference_id,
                    "created_at": n.created_at.strftime("%b %d, %Y - %I:%M %p"),
                }
                for n in rows
            ]

    @staticmethod
    def mark_as_read(notification_id: int) -> None:
        """Mark an individual notification as read."""
        with get_db() as session:
            notif = session.get(Notification, notification_id)
            if not notif:
                raise NotFoundException(f"Notification with ID {notification_id} not found.")
            notif.is_read = True
            session.commit()

    @staticmethod
    def mark_all_as_read() -> int:
        """Mark all unread notifications as read."""
        with get_db() as session:
            stmt = select(Notification).where(Notification.is_read == False)
            notifs = session.scalars(stmt).all()
            count = len(notifs)
            for n in notifs:
                n.is_read = True
            session.commit()
            return count

    @staticmethod
    def delete_notification(notification_id: int) -> None:
        """Permanently remove a notification."""
        with get_db() as session:
            notif = session.get(Notification, notification_id)
            if not notif:
                raise NotFoundException(f"Notification with ID {notification_id} not found.")
            session.delete(notif)
            session.commit()

    @staticmethod
    def clear_read_notifications() -> int:
        """Delete all read notifications to clean up database history."""
        with get_db() as session:
            stmt = select(Notification).where(Notification.is_read == True)
            notifs = session.scalars(stmt).all()
            count = len(notifs)
            for n in notifs:
                session.delete(n)
            session.commit()
            return count

    @staticmethod
    def create_notification(
        title: str,
        message: str,
        severity: str = "info",
        notif_type: str = "system",
        reference_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Manually broadcast or create a custom notification."""
        if not title.strip() or not message.strip():
            raise ValidationError("Title and message cannot be blank.")

        with get_db() as session:
            notif = Notification(
                type=notif_type,
                severity=severity,
                title=title.strip(),
                message=message.strip(),
                reference_id=reference_id,
                is_read=False,
            )
            session.add(notif)
            session.commit()
            session.refresh(notif)
            return {
                "id": notif.id,
                "title": notif.title,
                "severity": notif.severity,
                "is_read": notif.is_read,
            }
