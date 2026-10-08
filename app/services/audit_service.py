"""Audit trail logging and retrieval service."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.audit import AuditLog
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """Provides methods for recording and querying immutable audit events."""

    @staticmethod
    def log_action(
        user_id: Optional[int],
        username: str,
        action: str,
        module: str,
        description: str,
        ip_address: Optional[str] = "127.0.0.1",
    ) -> None:
        """Create a new audit log record within its own transaction."""
        try:
            with get_db() as session:
                log_entry = AuditLog(
                    user_id=user_id,
                    username=username or "system",
                    action=action.upper(),
                    module=module.upper(),
                    description=description,
                    ip_address=ip_address,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(log_entry)
            logger.info(f"Audit: [{module}] {action} by {username}: {description}")
        except Exception as e:
            # Audit failure must not crash the application, but must be logged
            logger.error(f"Failed to record audit log: {e}", exc_info=True)

    @staticmethod
    def get_audit_logs(
        limit: int = 200,
        module: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent audit logs with optional filtering."""
        with get_db() as session:
            stmt = select(AuditLog).order_by(desc(AuditLog.created_at))
            if module and module != "All":
                stmt = stmt.where(AuditLog.module == module.upper())
            if action and action != "All":
                stmt = stmt.where(AuditLog.action == action.upper())
            if user_id:
                stmt = stmt.where(AuditLog.user_id == user_id)

            stmt = stmt.limit(limit)
            results = session.scalars(stmt).all()

            logs_list = []
            for r in results:
                logs_list.append({
                    "id": r.id,
                    "timestamp": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                    "user_id": r.user_id,
                    "username": r.username,
                    "module": r.module,
                    "action": r.action,
                    "description": r.description,
                    "ip_address": r.ip_address,
                })
            return logs_list
