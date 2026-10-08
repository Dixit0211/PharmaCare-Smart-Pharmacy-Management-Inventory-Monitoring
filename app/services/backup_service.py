"""Database snapshot backup, integrity verification, and restoration service."""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple
from sqlalchemy import select, func
from app.core.config import settings
from app.core.database import get_db, engine
from app.core.exceptions import ValidationError, AppException
from app.services.auth_service import require_role
from app.services.audit_service import AuditService
from app.models.medicine import Medicine, MedicineBatch
from app.models.sale import Sale
from app.models.user import User
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.core.logging import get_logger

logger = get_logger(__name__)


class BackupService:
    """Provides hot-backup snapshot generation and restoration for the SQLite datastore."""

    @staticmethod
    def get_database_path() -> Path:
        """Resolve actual filesystem path of SQLite database."""
        db_url = settings.DATABASE_URL
        if "sqlite:///" in db_url:
            raw_path = db_url.replace("sqlite:///", "")
            return Path(raw_path).resolve()
        return Path("./data/pharmacare.db").resolve()

    @staticmethod
    def get_database_statistics() -> Dict[str, Any]:
        """Fetch file size, record counts, and last modification timestamp."""
        db_file = BackupService.get_database_path()
        size_kb = 0.0
        last_modified = "N/A"

        if db_file.exists():
            size_kb = round(db_file.stat().st_size / 1024, 2)
            last_modified = datetime.fromtimestamp(db_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        with get_db() as session:
            med_count = session.scalar(select(func.count(Medicine.id))) or 0
            batch_count = session.scalar(select(func.count(MedicineBatch.id))) or 0
            sale_count = session.scalar(select(func.count(Sale.id))) or 0
            customer_count = session.scalar(select(func.count(Customer.id))) or 0
            supplier_count = session.scalar(select(func.count(Supplier.id))) or 0
            user_count = session.scalar(select(func.count(User.id))) or 0

        return {
            "file_path": str(db_file),
            "file_size_kb": size_kb,
            "last_modified": last_modified,
            "total_medicines": med_count,
            "total_batches": batch_count,
            "total_sales": sale_count,
            "total_customers": customer_count,
            "total_suppliers": supplier_count,
            "total_users": user_count,
        }

    @staticmethod
    @require_role("admin")
    def create_database_backup(current_user: Dict[str, Any]) -> Tuple[bytes, str]:
        """
        Create a clean SQLite hot backup using the SQLite backup API
        to prevent partial writes during active operations.
        Returns binary content and suggested filename.
        """
        db_path = BackupService.get_database_path()
        if not db_path.exists():
            raise AppException("Database file does not exist on disk.")

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pharmacare_backup_{timestamp_str}.db"

        # Create safe in-memory or temporary backup via sqlite3
        temp_backup_path = db_path.parent / f"temp_{filename}"
        try:
            src_conn = sqlite3.connect(str(db_path))
            dst_conn = sqlite3.connect(str(temp_backup_path))
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            with open(temp_backup_path, "rb") as f:
                backup_bytes = f.read()

            if temp_backup_path.exists():
                os.remove(temp_backup_path)

            AuditService.log_action(
                user_id=current_user.get("id"),
                username=current_user.get("username", "admin"),
                action="BACKUP",
                module="DATABASE",
                description=f"Exported system database snapshot '{filename}' ({len(backup_bytes)} bytes)",
            )

            return backup_bytes, filename

        except Exception as e:
            if temp_backup_path.exists():
                os.remove(temp_backup_path)
            logger.error(f"Error creating database backup: {e}", exc_info=True)
            raise AppException(f"Failed to generate backup: {str(e)}")

    @staticmethod
    @require_role("admin")
    def restore_database_backup(current_user: Dict[str, Any], backup_bytes: bytes) -> bool:
        """
        Safely restores database from uploaded SQLite binary:
        1. Validates SQLite header (magic bytes).
        2. Validates essential tables exist (users, medicines, sales).
        3. Creates safety fallback copy of current database.
        4. Overwrites database file and disposes existing engine connection pools.
        """
        if not backup_bytes or len(backup_bytes) < 100:
            raise ValidationError("Invalid backup file: file is empty or corrupted.")

        # SQLite database header check ("SQLite format 3\000")
        if not backup_bytes.startswith(b"SQLite format 3"):
            raise ValidationError("Uploaded file is not a valid SQLite database format.")

        db_path = BackupService.get_database_path()
        db_dir = db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)

        temp_restore_path = db_dir / "temp_restore_candidate.db"
        safety_copy_path = db_dir / f"safety_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

        try:
            # 1. Write candidate to temporary file
            with open(temp_restore_path, "wb") as f:
                f.write(backup_bytes)

            # 2. Verify candidate database schema integrity
            conn = sqlite3.connect(str(temp_restore_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            required_tables = ["users", "medicines", "medicine_batches", "sales"]
            missing = [t for t in required_tables if t not in tables]
            if missing:
                raise ValidationError(f"Backup file is incompatible: missing required tables {missing}.")

            # 3. Create safety copy of current live database
            if db_path.exists():
                shutil.copy2(db_path, safety_copy_path)

            # 4. Dispose active connection pools so SQLite file handle is free on Windows
            engine.dispose()

            # 5. Overwrite current DB with restored file
            shutil.copy2(temp_restore_path, db_path)

            if temp_restore_path.exists():
                os.remove(temp_restore_path)

            AuditService.log_action(
                user_id=current_user.get("id"),
                username=current_user.get("username", "admin"),
                action="RESTORE",
                module="DATABASE",
                description="Database successfully restored from backup snapshot.",
            )
            logger.info("Database successfully restored from uploaded backup.")
            return True

        except Exception as e:
            if temp_restore_path.exists():
                os.remove(temp_restore_path)
            logger.error(f"Error restoring database: {e}", exc_info=True)
            raise AppException(f"Restoration failed: {str(e)}")
