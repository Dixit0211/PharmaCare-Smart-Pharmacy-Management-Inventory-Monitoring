"""Batch-level physical inventory and FEFO dispensing service."""

from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, desc, asc
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    ConflictException,
    ExpiredBatchError,
)
from app.models.medicine import Medicine, MedicineBatch
from app.models.sale import SaleItem
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class BatchService:
    """Business logic for physical batch-level stock, expiry, and FEFO sorting."""

    @staticmethod
    def list_batches(
        medicine_id: Optional[int] = None,
        include_expired: bool = True,
    ) -> List[Dict[str, Any]]:
        """List physical batches with dynamic expiry days remaining and status tags."""
        today = date.today()

        with get_db() as session:
            stmt = (
                select(
                    MedicineBatch,
                    Medicine.name.label("medicine_name"),
                    Medicine.strength.label("medicine_strength"),
                    Medicine.dosage_form.label("dosage_form"),
                )
                .join(Medicine, MedicineBatch.medicine_id == Medicine.id)
                .order_by(MedicineBatch.expiry_date.asc())
            )

            if medicine_id:
                stmt = stmt.where(MedicineBatch.medicine_id == medicine_id)

            if not include_expired:
                stmt = stmt.where(MedicineBatch.expiry_date >= today)

            rows = session.execute(stmt).all()

            batches_data = []
            for b, med_name, med_strength, d_form in rows:
                days_left = (b.expiry_date - today).days

                if b.expiry_date < today:
                    status = "expired"
                elif days_left <= 30:
                    status = "expiring_soon"
                else:
                    status = "safe"

                batches_data.append({
                    "id": b.id,
                    "medicine_id": b.medicine_id,
                    "medicine_name": f"{med_name} ({med_strength})",
                    "dosage_form": d_form,
                    "batch_no": b.batch_no,
                    "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
                    "days_remaining": days_left,
                    "quantity": b.quantity,
                    "purchase_price": b.purchase_price,
                    "status": status,
                    "created_at": b.created_at.strftime("%Y-%m-%d") if b.created_at else "",
                })

            return batches_data

    @staticmethod
    def get_batch(batch_id: int) -> Dict[str, Any]:
        """Fetch single batch details."""
        today = date.today()
        with get_db() as session:
            b = session.get(MedicineBatch, batch_id)
            if not b:
                raise NotFoundException(f"Batch with ID {batch_id} not found.")

            days_left = (b.expiry_date - today).days
            status = "expired" if b.expiry_date < today else ("expiring_soon" if days_left <= 30 else "safe")

            return {
                "id": b.id,
                "medicine_id": b.medicine_id,
                "medicine_name": b.medicine.name if b.medicine else "",
                "batch_no": b.batch_no,
                "expiry_date": b.expiry_date,
                "days_remaining": days_left,
                "quantity": b.quantity,
                "purchase_price": b.purchase_price,
                "status": status,
            }

    @staticmethod
    def create_batch(
        current_user: Dict[str, Any],
        medicine_id: int,
        batch_no: str,
        expiry_date_val: date,
        quantity: int,
        purchase_price: float,
    ) -> Dict[str, Any]:
        """Add a new physical batch for a medicine."""
        batch_no = (batch_no or "").strip().upper()
        if not batch_no:
            raise ValidationError("Batch number is required.")

        if not expiry_date_val:
            raise ValidationError("Expiry date is required.")

        if quantity < 0:
            raise ValidationError("Initial quantity cannot be negative.")

        if purchase_price < 0:
            raise ValidationError("Purchase price cannot be negative.")

        with get_db() as session:
            med = session.get(Medicine, medicine_id)
            if not med:
                raise NotFoundException(f"Medicine with ID {medicine_id} not found.")

            # Check unique constraint on (medicine_id, batch_no)
            existing = session.scalars(
                select(MedicineBatch).where(
                    (MedicineBatch.medicine_id == medicine_id)
                    & (MedicineBatch.batch_no == batch_no)
                )
            ).first()
            if existing:
                raise ConflictException(f"Batch '{batch_no}' already exists for {med.name}.")

            batch = MedicineBatch(
                medicine_id=medicine_id,
                batch_no=batch_no,
                expiry_date=expiry_date_val,
                quantity=quantity,
                purchase_price=purchase_price,
            )
            session.add(batch)
            session.flush()
            new_id = batch.id
            med_name = med.name

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CREATE",
            module="INVENTORY",
            description=f"Created batch '{batch_no}' for '{med_name}' (Qty: {quantity}, Exp: {expiry_date_val})",
        )

        return {"id": new_id, "batch_no": batch_no, "quantity": quantity}

    @staticmethod
    def update_batch(
        current_user: Dict[str, Any],
        batch_id: int,
        quantity: int,
        purchase_price: float,
        expiry_date_val: date,
    ) -> Dict[str, Any]:
        """Update existing batch quantities or expiry."""
        if quantity < 0:
            raise ValidationError("Quantity cannot be negative.")

        if purchase_price < 0:
            raise ValidationError("Purchase price cannot be negative.")

        with get_db() as session:
            batch = session.get(MedicineBatch, batch_id)
            if not batch:
                raise NotFoundException(f"Batch with ID {batch_id} not found.")

            old_qty = batch.quantity
            batch.quantity = quantity
            batch.purchase_price = purchase_price
            batch.expiry_date = expiry_date_val
            b_no = batch.batch_no
            med_name = batch.medicine.name if batch.medicine else "Medicine"

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="UPDATE",
            module="INVENTORY",
            description=f"Updated batch '{b_no}' for '{med_name}': Qty {old_qty} -> {quantity}, Exp: {expiry_date_val}",
        )

        return {"id": batch_id, "batch_no": b_no, "quantity": quantity}

    @staticmethod
    def adjust_batch_stock(
        current_user: Dict[str, Any],
        batch_id: int,
        new_quantity: int,
        reason: str,
    ) -> Dict[str, Any]:
        """Manually adjust stock for audits, damage, or discrepancy with mandatory reason."""
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("A specific reason is required for manual stock adjustments.")

        if new_quantity < 0:
            raise ValidationError("Stock quantity cannot be negative.")

        with get_db() as session:
            batch = session.get(MedicineBatch, batch_id)
            if not batch:
                raise NotFoundException(f"Batch with ID {batch_id} not found.")

            old_qty = batch.quantity
            diff = new_quantity - old_qty
            batch.quantity = new_quantity
            b_no = batch.batch_no
            med_name = batch.medicine.name if batch.medicine else "Medicine"

        diff_str = f"+{diff}" if diff >= 0 else f"{diff}"
        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="STOCK_ADJUSTMENT",
            module="INVENTORY",
            description=f"Adjusted batch '{b_no}' ({med_name}): {old_qty} -> {new_quantity} ({diff_str}). Reason: {reason}",
        )

        return {"id": batch_id, "old_quantity": old_qty, "new_quantity": new_quantity}

    @staticmethod
    def delete_batch(current_user: Dict[str, Any], batch_id: int) -> None:
        """Delete batch if never used in dispensing sales."""
        with get_db() as session:
            batch = session.get(MedicineBatch, batch_id)
            if not batch:
                raise NotFoundException(f"Batch with ID {batch_id} not found.")

            # Check if used in sales
            sales_count = session.scalars(
                select(func.count(SaleItem.id)).where(SaleItem.batch_id == batch_id)
            ).one()

            if sales_count > 0:
                raise ConflictException(
                    f"Cannot delete batch '{batch.batch_no}' because {sales_count} sale(s) have dispensed units from it. Set quantity to 0 instead."
                )

            b_no = batch.batch_no
            med_name = batch.medicine.name if batch.medicine else "Medicine"
            session.delete(batch)

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="DELETE",
            module="INVENTORY",
            description=f"Deleted batch '{b_no}' for '{med_name}'",
        )

    @staticmethod
    def get_available_batches_for_sale(medicine_id: int) -> List[Dict[str, Any]]:
        """
        Return non-expired batches with positive stock sorted FEFO (First-Expiry-First-Out).
        Expired batches are strictly excluded.
        """
        today = date.today()
        with get_db() as session:
            stmt = (
                select(MedicineBatch)
                .where(
                    (MedicineBatch.medicine_id == medicine_id)
                    & (MedicineBatch.expiry_date >= today)
                    & (MedicineBatch.quantity > 0)
                )
                .order_by(MedicineBatch.expiry_date.asc())
            )
            batches = session.scalars(stmt).all()

            return [
                {
                    "id": b.id,
                    "batch_no": b.batch_no,
                    "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
                    "days_remaining": (b.expiry_date - today).days,
                    "quantity": b.quantity,
                    "purchase_price": b.purchase_price,
                }
                for b in batches
            ]
