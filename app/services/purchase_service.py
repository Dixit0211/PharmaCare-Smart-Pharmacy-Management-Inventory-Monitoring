"""Procurement purchase order and inward stock intake service."""

from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, desc, or_
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    ConflictException,
)
from app.models.purchase import Purchase, PurchaseItem
from app.models.supplier import Supplier
from app.models.medicine import Medicine, MedicineBatch
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class PurchaseService:
    """Business logic for stock purchases and automated batch inventory creation."""

    @staticmethod
    def list_purchases(
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List purchase orders with supplier metadata and item counts."""
        with get_db() as session:
            stmt = (
                select(
                    Purchase,
                    Supplier.name.label("supplier_name"),
                    func.count(PurchaseItem.id).label("item_count"),
                )
                .join(Supplier, Purchase.supplier_id == Supplier.id)
                .outerjoin(PurchaseItem, Purchase.id == PurchaseItem.purchase_id)
                .group_by(Purchase.id)
                .order_by(desc(Purchase.purchase_date), desc(Purchase.id))
            )

            if supplier_id:
                stmt = stmt.where(Purchase.supplier_id == supplier_id)

            if status and status != "All":
                stmt = stmt.where(Purchase.status == status.lower())

            if search:
                term = f"%{search.strip().lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Purchase.invoice_no).like(term),
                        func.lower(Supplier.name).like(term),
                    )
                )

            rows = session.execute(stmt).all()

            purchases = []
            for p, sup_name, it_count in rows:
                purchases.append({
                    "id": p.id,
                    "invoice_no": p.invoice_no,
                    "supplier_id": p.supplier_id,
                    "supplier_name": sup_name,
                    "purchase_date": p.purchase_date.strftime("%Y-%m-%d"),
                    "total_amount": round(p.total_amount, 2),
                    "item_count": it_count,
                    "status": p.status,
                    "notes": p.notes or "-",
                    "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
                })
            return purchases

    @staticmethod
    def get_purchase(purchase_id: int) -> Dict[str, Any]:
        """Retrieve full purchase order with line items."""
        with get_db() as session:
            p = session.get(Purchase, purchase_id)
            if not p:
                raise NotFoundException(f"Purchase order with ID {purchase_id} not found.")

            items = []
            for it in p.items:
                med_name = it.medicine.name if it.medicine else "Unknown Medicine"
                strength = it.medicine.strength if it.medicine else ""
                items.append({
                    "id": it.id,
                    "medicine_id": it.medicine_id,
                    "medicine_name": f"{med_name} ({strength})",
                    "batch_no": it.batch_no,
                    "expiry_date": it.expiry_date.strftime("%Y-%m-%d"),
                    "quantity": it.quantity,
                    "purchase_price": it.purchase_price,
                    "subtotal": it.subtotal,
                })

            return {
                "id": p.id,
                "invoice_no": p.invoice_no,
                "supplier_id": p.supplier_id,
                "supplier_name": p.supplier.name if p.supplier else "Unknown",
                "supplier_phone": p.supplier.phone if p.supplier else "-",
                "supplier_gst": p.supplier.gst_number if p.supplier else "-",
                "purchase_date": p.purchase_date.strftime("%Y-%m-%d"),
                "total_amount": round(p.total_amount, 2),
                "status": p.status,
                "notes": p.notes or "",
                "items": items,
            }

    @staticmethod
    def create_purchase_order(
        current_user: Dict[str, Any],
        supplier_id: int,
        invoice_no: str,
        purchase_date_val: date,
        items: List[Dict[str, Any]],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record inward stock purchase and create/increment physical batch inventory.
        Rule 3: Completing a purchase creates or increases a batch.
        """
        invoice_no = (invoice_no or "").strip().upper()
        if not invoice_no:
            raise ValidationError("Supplier Invoice Number is mandatory.")

        if not supplier_id:
            raise ValidationError("Please select a valid supplier.")

        if not purchase_date_val:
            raise ValidationError("Purchase date is required.")

        if not items or len(items) == 0:
            raise ValidationError("A purchase invoice must contain at least one medicine item.")

        today = date.today()

        with get_db() as session:
            # Check supplier
            sup = session.get(Supplier, supplier_id)
            if not sup:
                raise ValidationError("Specified supplier does not exist.")

            # Check unique invoice number
            existing_inv = session.scalars(
                select(Purchase).where(Purchase.invoice_no == invoice_no)
            ).first()
            if existing_inv:
                raise ConflictException(f"Purchase invoice '{invoice_no}' already exists in the system.")

            total_amount = 0.0
            purchase_items_to_add = []

            # Process each line item and update batch inventory
            for item in items:
                med_id = item.get("medicine_id")
                batch_no = (item.get("batch_no") or "").strip().upper()
                exp_date = item.get("expiry_date")
                qty = int(item.get("quantity", 0))
                p_price = float(item.get("purchase_price", 0.0))

                if not med_id:
                    raise ValidationError("Medicine ID missing in line item.")

                med = session.get(Medicine, med_id)
                if not med:
                    raise ValidationError(f"Medicine with ID {med_id} not found.")

                if not batch_no:
                    raise ValidationError(f"Batch number is required for {med.name}.")

                if not exp_date:
                    raise ValidationError(f"Expiry date is required for batch {batch_no}.")

                # Convert string date if necessary
                if isinstance(exp_date, str):
                    exp_date = date.fromisoformat(exp_date)

                if exp_date < today:
                    raise ValidationError(
                        f"Cannot procure expired batch '{batch_no}' for {med.name} (Expiry: {exp_date})."
                    )

                if qty <= 0:
                    raise ValidationError(f"Quantity for {med.name} (Batch {batch_no}) must be strictly > 0.")

                if p_price < 0:
                    raise ValidationError(f"Purchase price for {med.name} cannot be negative.")

                line_subtotal = round(qty * p_price, 2)
                total_amount += line_subtotal

                # Check if batch already exists: increment stock or create new batch
                batch = session.scalars(
                    select(MedicineBatch).where(
                        (MedicineBatch.medicine_id == med_id)
                        & (MedicineBatch.batch_no == batch_no)
                    )
                ).first()

                if batch:
                    batch.quantity += qty
                    batch.purchase_price = p_price
                    batch.expiry_date = exp_date
                else:
                    batch = MedicineBatch(
                        medicine_id=med_id,
                        batch_no=batch_no,
                        expiry_date=exp_date,
                        quantity=qty,
                        purchase_price=p_price,
                    )
                    session.add(batch)

                purchase_items_to_add.append({
                    "medicine_id": med_id,
                    "batch_no": batch_no,
                    "expiry_date": exp_date,
                    "quantity": qty,
                    "purchase_price": p_price,
                    "subtotal": line_subtotal,
                })

            total_amount = round(total_amount, 2)

            purchase = Purchase(
                supplier_id=supplier_id,
                invoice_no=invoice_no,
                purchase_date=purchase_date_val,
                total_amount=total_amount,
                status="received",
                notes=(notes or "").strip() or None,
            )
            session.add(purchase)
            session.flush()

            for p_item in purchase_items_to_add:
                pi = PurchaseItem(
                    purchase_id=purchase.id,
                    medicine_id=p_item["medicine_id"],
                    batch_no=p_item["batch_no"],
                    expiry_date=p_item["expiry_date"],
                    quantity=p_item["quantity"],
                    purchase_price=p_item["purchase_price"],
                    subtotal=p_item["subtotal"],
                )
                session.add(pi)

            sup_name = sup.name
            new_id = purchase.id

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CREATE",
            module="PURCHASE",
            description=f"Received purchase invoice '{invoice_no}' from '{sup_name}' ({len(items)} items, Total: ₹{total_amount:.2f})",
        )

        return {"id": new_id, "invoice_no": invoice_no, "total_amount": total_amount}

    @staticmethod
    def cancel_purchase_order(current_user: Dict[str, Any], purchase_id: int, reason: str) -> None:
        """
        Cancel a purchase order and reverse added batch stock.
        Prevents cancellation if units have already been sold.
        """
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Reason for cancelling purchase invoice is mandatory.")

        with get_db() as session:
            p = session.get(Purchase, purchase_id)
            if not p:
                raise NotFoundException(f"Purchase order with ID {purchase_id} not found.")

            if p.status == "cancelled":
                raise ValidationError("Purchase invoice is already cancelled.")

            # Verify stock availability for reversal
            for it in p.items:
                batch = session.scalars(
                    select(MedicineBatch).where(
                        (MedicineBatch.medicine_id == it.medicine_id)
                        & (MedicineBatch.batch_no == it.batch_no)
                    )
                ).first()

                if not batch or batch.quantity < it.quantity:
                    med_name = it.medicine.name if it.medicine else "Medicine"
                    raise ConflictException(
                        f"Cannot cancel purchase: units of batch '{it.batch_no}' ({med_name}) have already been dispensed in sales."
                    )

                batch.quantity -= it.quantity

            p.status = "cancelled"
            inv_no = p.invoice_no
            sup_name = p.supplier.name if p.supplier else "Supplier"

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CANCEL",
            module="PURCHASE",
            description=f"Cancelled purchase invoice '{inv_no}' ({sup_name}). Reason: {reason}",
        )
