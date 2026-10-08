"""Inventory monitoring service for expiry tracking, quarantine, and low-stock reorder algorithms."""

from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import io
import csv
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.core.exceptions import ValidationError, NotFoundException
from app.models.medicine import Medicine, MedicineBatch
from app.models.category import Category
from app.models.setting import AppSetting
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class InventoryService:
    """Business logic for expiry quarantine, FEFO prioritization, and low-stock replenishment."""

    @staticmethod
    def get_expiry_warning_days() -> int:
        """Fetch configured expiry warning threshold from settings (default 30 days)."""
        with get_db() as session:
            setting = session.scalars(
                select(AppSetting).where(AppSetting.key == "expiry_warning_days")
            ).first()
            if setting and setting.value.isdigit():
                return int(setting.value)
            return 30

    @staticmethod
    def get_expiry_overview(warning_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Compute real-time expiry categorization:
        - Expired: expiry_date < today
        - Expiring Soon: today <= expiry_date <= today + warning_days
        - Safe: expiry_date > today + warning_days
        """
        today = date.today()
        days_threshold = warning_days or InventoryService.get_expiry_warning_days()
        threshold_date = today + timedelta(days=days_threshold)

        with get_db() as session:
            stmt = (
                select(
                    MedicineBatch,
                    Medicine.name.label("medicine_name"),
                    Medicine.generic_name.label("generic_name"),
                    Medicine.strength.label("strength"),
                    Medicine.dosage_form.label("dosage_form"),
                    Category.name.label("category_name"),
                )
                .join(Medicine, MedicineBatch.medicine_id == Medicine.id)
                .join(Category, Medicine.category_id == Category.id)
                .order_by(MedicineBatch.expiry_date.asc())
            )
            rows = session.execute(stmt).all()

            expired_items = []
            expiring_soon_items = []
            safe_items = []

            total_expired_units = 0
            total_expired_loss_value = 0.0
            total_near_expiry_units = 0
            total_near_expiry_value = 0.0

            for b, med_name, gen_name, strength, d_form, cat_name in rows:
                days_left = (b.expiry_date - today).days
                batch_loss_val = round(b.quantity * b.purchase_price, 2)

                item = {
                    "batch_id": b.id,
                    "medicine_id": b.medicine_id,
                    "medicine_name": f"{med_name} ({strength})",
                    "generic_name": gen_name,
                    "category": cat_name,
                    "dosage_form": d_form,
                    "batch_no": b.batch_no,
                    "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
                    "days_remaining": days_left,
                    "quantity": b.quantity,
                    "purchase_price": b.purchase_price,
                    "total_value": batch_loss_val,
                }

                if b.expiry_date < today:
                    item["status"] = "expired"
                    item["urgency"] = "QUARANTINED"
                    expired_items.append(item)
                    total_expired_units += b.quantity
                    total_expired_loss_value += batch_loss_val
                elif b.expiry_date <= threshold_date:
                    item["status"] = "expiring_soon"
                    if days_left <= 15:
                        item["urgency"] = "CRITICAL (<=15d)"
                    else:
                        item["urgency"] = "WARNING (<=30d)"
                    expiring_soon_items.append(item)
                    total_near_expiry_units += b.quantity
                    total_near_expiry_value += batch_loss_val
                else:
                    item["status"] = "safe"
                    item["urgency"] = "NORMAL"
                    safe_items.append(item)

            return {
                "warning_days_configured": days_threshold,
                "total_batches_count": len(rows),
                "expired_batches_count": len(expired_items),
                "expired_units_total": total_expired_units,
                "expired_loss_value": round(total_expired_loss_value, 2),
                "expiring_soon_batches_count": len(expiring_soon_items),
                "expiring_soon_units_total": total_near_expiry_units,
                "expiring_soon_value": round(total_near_expiry_value, 2),
                "safe_batches_count": len(safe_items),
                "expired_batches": expired_items,
                "expiring_soon_batches": expiring_soon_items,
                "safe_batches": safe_items,
                "all_batches": expired_items + expiring_soon_items + safe_items,
            }

    @staticmethod
    def quarantine_and_discard_batch(
        current_user: Dict[str, Any],
        batch_id: int,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Quarantine and discard an expired batch by zeroing its quantity
        and logging an audited record for regulatory compliance.
        """
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Reason for batch disposal / quarantine is mandatory.")

        with get_db() as session:
            batch = session.get(MedicineBatch, batch_id)
            if not batch:
                raise NotFoundException(f"Batch with ID {batch_id} not found.")

            discarded_qty = batch.quantity
            loss_val = round(discarded_qty * batch.purchase_price, 2)
            b_no = batch.batch_no
            med_name = batch.medicine.name if batch.medicine else "Medicine"

            batch.quantity = 0

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="DISCARD_EXPIRED",
            module="INVENTORY",
            description=f"Discarded {discarded_qty} units of expired batch '{b_no}' ({med_name}) - Estimated loss: ₹{loss_val:.2f}. Reason: {reason}",
        )

        return {
            "batch_id": batch_id,
            "batch_no": b_no,
            "discarded_quantity": discarded_qty,
            "loss_value": loss_val,
        }

    @staticmethod
    def get_low_stock_overview() -> Dict[str, Any]:
        """
        Analyze all medicines against reorder thresholds:
        - Low stock: total available non-expired stock <= min_stock
        - Out of stock: total available non-expired stock == 0
        - Calculates suggested replenishment reorder quantity
        """
        today = date.today()

        with get_db() as session:
            stmt = (
                select(
                    Medicine,
                    Category.name.label("category_name"),
                )
                .join(Category, Medicine.category_id == Category.id)
                .where(Medicine.status == "active")
                .order_by(Medicine.name.asc())
            )
            rows = session.execute(stmt).all()

            low_stock_items = []
            out_of_stock_count = 0
            low_stock_count = 0
            total_reorder_qty = 0
            total_reorder_est_cost = 0.0

            for med, cat_name in rows:
                # Sum only non-expired batches
                current_stock = sum(
                    b.quantity for b in med.batches if b.expiry_date >= today
                )

                if current_stock <= med.min_stock:
                    if current_stock == 0:
                        out_of_stock_count += 1
                        severity = "critical"
                    else:
                        low_stock_count += 1
                        severity = "warning"

                    # Calculate suggested reorder quantity (e.g. target 2x min_stock)
                    target_stock = max(med.min_stock * 2, 30)
                    suggested_qty = max(target_stock - current_stock, med.min_stock)

                    # Estimate cost using latest batch purchase price or default 60% of selling price
                    latest_batch = next((b for b in reversed(med.batches) if b.purchase_price > 0), None)
                    unit_cost = latest_batch.purchase_price if latest_batch else round(med.selling_price * 0.65, 2)
                    est_total_cost = round(suggested_qty * unit_cost, 2)

                    total_reorder_qty += suggested_qty
                    total_reorder_est_cost += est_total_cost

                    low_stock_items.append({
                        "medicine_id": med.id,
                        "medicine_name": f"{med.name} ({med.strength})",
                        "generic_name": med.generic_name,
                        "category": cat_name,
                        "dosage_form": med.dosage_form,
                        "manufacturer": med.manufacturer or "-",
                        "current_stock": current_stock,
                        "min_stock": med.min_stock,
                        "deficit": med.min_stock - current_stock,
                        "suggested_reorder_qty": suggested_qty,
                        "est_unit_cost": unit_cost,
                        "est_total_cost": est_total_cost,
                        "severity": severity,
                        "prescription_required": med.prescription_required,
                    })

            # Sort by deficit desc (most critical first)
            low_stock_items.sort(key=lambda x: (x["current_stock"], -x["deficit"]))

            return {
                "total_low_stock_items": len(low_stock_items),
                "out_of_stock_count": out_of_stock_count,
                "below_threshold_count": low_stock_count,
                "total_suggested_reorder_units": total_reorder_qty,
                "total_estimated_reorder_cost": round(total_reorder_est_cost, 2),
                "items": low_stock_items,
            }

    @staticmethod
    def update_medicine_min_stock(
        current_user: Dict[str, Any],
        medicine_id: int,
        new_min_stock: int,
    ) -> None:
        """Update the minimum stock threshold for a medicine."""
        if new_min_stock < 0:
            raise ValidationError("Minimum stock threshold cannot be negative.")

        with get_db() as session:
            med = session.get(Medicine, medicine_id)
            if not med:
                raise NotFoundException(f"Medicine with ID {medicine_id} not found.")

            old_min = med.min_stock
            med.min_stock = new_min_stock
            med_name = med.name

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="UPDATE_THRESHOLD",
            module="INVENTORY",
            description=f"Updated reorder min_stock for '{med_name}': {old_min} -> {new_min_stock} units",
        )

    @staticmethod
    def export_expiry_report_csv(warning_days: Optional[int] = None) -> str:
        """Generate formatted CSV string for statutory expiry and quarantine report."""
        overview = InventoryService.get_expiry_overview(warning_days)
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Batch ID", "Medicine", "Category", "Batch Number", "Expiry Date", "Days Remaining", "Quantity", "Purchase Price (INR)", "Total Value (INR)", "Status", "Urgency"])

        for b in overview["all_batches"]:
            writer.writerow([
                b["batch_id"],
                b["medicine_name"],
                b["category"],
                b["batch_no"],
                b["expiry_date"],
                b["days_remaining"],
                b["quantity"],
                f"{b['purchase_price']:.2f}",
                f"{b['total_value']:.2f}",
                b["status"].upper(),
                b["urgency"],
            ])

        return output.getvalue()

    @staticmethod
    def export_low_stock_csv() -> str:
        """Generate formatted CSV string for low-stock reorder procurement."""
        overview = InventoryService.get_low_stock_overview()
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Medicine ID", "Medicine Name", "Generic Name", "Category", "Dosage Form", "Current Non-Expired Stock", "Min Stock Threshold", "Deficit", "Suggested Reorder Qty", "Est Unit Cost (INR)", "Est Total Cost (INR)", "Severity"])

        for item in overview["items"]:
            writer.writerow([
                item["medicine_id"],
                item["medicine_name"],
                item["generic_name"],
                item["category"],
                item["dosage_form"],
                item["current_stock"],
                item["min_stock"],
                item["deficit"],
                item["suggested_reorder_qty"],
                f"{item['est_unit_cost']:.2f}",
                f"{item['est_total_cost']:.2f}",
                item["severity"].upper(),
            ])

        return output.getvalue()
