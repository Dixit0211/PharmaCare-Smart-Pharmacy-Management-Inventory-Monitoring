"""Point of Sale (POS) billing, FEFO batch deduction, and sales history service."""

from datetime import date, datetime, timezone
from typing import List, Dict, Any, Optional
import random
from sqlalchemy import select, func, desc, or_
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    InsufficientStockError,
    ExpiredBatchError,
)
from app.models.sale import Sale, SaleItem
from app.models.customer import Customer
from app.models.prescription import Prescription
from app.models.medicine import Medicine, MedicineBatch
from app.models.user import User
from app.models.setting import AppSetting
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class SaleService:
    """Business logic for pharmacy counter billing, FEFO batch allocation, and sales transactions."""

    @staticmethod
    def generate_next_invoice_number() -> str:
        """Generate formatted invoice number like INV-2026-1048."""
        year = datetime.now().year
        with get_db() as session:
            count = session.scalars(select(func.count(Sale.id))).one()
            return f"INV-{year}-{1001 + count}"

    @staticmethod
    def create_sale(
        current_user: Dict[str, Any],
        cart_items: List[Dict[str, Any]],
        customer_id: Optional[int] = None,
        prescription_id: Optional[int] = None,
        payment_method: str = "Cash",
        discount_percent: float = 0.0,
        tax_percent: float = 5.0,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute atomic sales checkout:
        1. Validates cart non-empty and quantities > 0.
        2. Enforces Schedule H doctor prescription check for Rx medications.
        3. Enforces statutory expiry quarantine (expired batches rejected).
        4. Enforces available stock sufficiency and executes FEFO stock reduction.
        5. Computes historical purchase cost and records Sale & SaleItem entities.
        6. Logs immutable audit trail.
        """
        if not cart_items or len(cart_items) == 0:
            raise ValidationError("Billing cart is empty. Please add at least one medicine.")

        if not current_user or not current_user.get("id"):
            raise ValidationError("User authentication context required for cashier billing.")

        discount_percent = max(0.0, min(100.0, float(discount_percent or 0.0)))
        tax_percent = max(0.0, float(tax_percent or 0.0))
        today = date.today()
        now_dt = datetime.now(timezone.utc)

        with get_db() as session:
            # 1. Verify customer and prescription if provided
            customer_obj = session.get(Customer, customer_id) if customer_id else None
            prescription_obj = session.get(Prescription, prescription_id) if prescription_id else None

            # 2. Check if any cart item requires prescription (Schedule H)
            for it in cart_items:
                med_id = it.get("medicine_id")
                med = session.get(Medicine, med_id)
                if not med:
                    raise NotFoundException(f"Medicine with ID {med_id} not found.")

                # Rule 6: Prescription-required medicines need a valid prescription record
                if med.prescription_required and not prescription_id:
                    raise ValidationError(
                        f"Prescription required: '{med.name}' is a Schedule H/X medication. Please attach a valid prescription before completing sale."
                    )

            # 3. Process each line item with FEFO stock deduction
            subtotal = 0.0
            total_profit = 0.0
            sale_items_records = []

            for it in cart_items:
                med_id = it["medicine_id"]
                req_qty = int(it.get("quantity", 1))
                explicit_batch_id = it.get("batch_id")

                if req_qty <= 0:
                    raise ValidationError(f"Quantity for {it.get('medicine_name', 'item')} must be at least 1 unit.")

                med = session.get(Medicine, med_id)
                unit_price = float(it.get("unit_price", med.selling_price))

                if explicit_batch_id:
                    # Specific batch chosen by pharmacist
                    batch = session.get(MedicineBatch, explicit_batch_id)
                    if not batch or batch.medicine_id != med_id:
                        raise NotFoundException("Selected batch does not match product.")

                    # Rule 1: Expired batches can never be sold
                    if batch.expiry_date < today:
                        raise ExpiredBatchError(
                            f"Cannot dispense expired batch '{batch.batch_no}' for {med.name} (Expired on {batch.expiry_date})."
                        )

                    # Rule 2: Sale qty must be <= available stock
                    if batch.quantity < req_qty:
                        raise InsufficientStockError(
                            f"Insufficient stock in batch '{batch.batch_no}' ({med.name}). Available: {batch.quantity}, Requested: {req_qty}."
                        )

                    # Deduct batch stock
                    batch.quantity -= req_qty
                    line_subtotal = round(req_qty * unit_price, 2)
                    subtotal += line_subtotal
                    total_profit += (unit_price - batch.purchase_price) * req_qty

                    sale_items_records.append({
                        "medicine_id": med_id,
                        "medicine_name": med.name,
                        "batch_id": batch.id,
                        "batch_no": batch.batch_no,
                        "expiry_date": batch.expiry_date.strftime("%Y-%m-%d"),
                        "quantity": req_qty,
                        "unit_price": unit_price,
                        "purchase_price": batch.purchase_price,
                        "subtotal": line_subtotal,
                    })

                else:
                    # Automatic FEFO Allocation (First-Expiry-First-Out)
                    available_batches = session.scalars(
                        select(MedicineBatch)
                        .where(
                            (MedicineBatch.medicine_id == med_id)
                            & (MedicineBatch.expiry_date >= today)
                            & (MedicineBatch.quantity > 0)
                        )
                        .order_by(MedicineBatch.expiry_date.asc())
                    ).all()

                    total_avail = sum(b.quantity for b in available_batches)
                    if total_avail < req_qty:
                        raise InsufficientStockError(
                            f"Insufficient sellable stock for '{med.name}'. Available: {total_avail} units, Requested: {req_qty} units."
                        )

                    remaining_to_deduct = req_qty
                    for b in available_batches:
                        if remaining_to_deduct == 0:
                            break

                        deduct_qty = min(b.quantity, remaining_to_deduct)
                        b.quantity -= deduct_qty
                        remaining_to_deduct -= deduct_qty

                        line_subtotal = round(deduct_qty * unit_price, 2)
                        subtotal += line_subtotal
                        total_profit += (unit_price - b.purchase_price) * deduct_qty

                        sale_items_records.append({
                            "medicine_id": med_id,
                            "medicine_name": med.name,
                            "batch_id": b.id,
                            "batch_no": b.batch_no,
                            "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
                            "quantity": deduct_qty,
                            "unit_price": unit_price,
                            "purchase_price": b.purchase_price,
                            "subtotal": line_subtotal,
                        })

            # Calculate financial totals
            subtotal = round(subtotal, 2)
            discount_amount = round(subtotal * (discount_percent / 100.0), 2)
            taxable_base = subtotal - discount_amount
            tax_amount = round(taxable_base * (tax_percent / 100.0), 2)
            grand_total = round(taxable_base + tax_amount, 2)

            invoice_no = SaleService.generate_next_invoice_number()

            sale = Sale(
                invoice_no=invoice_no,
                customer_id=customer_id,
                prescription_id=prescription_id,
                user_id=current_user["id"],
                payment_method=payment_method,
                subtotal=subtotal,
                discount=discount_amount,
                tax=tax_amount,
                total_amount=grand_total,
                sale_date=now_dt,
                notes=notes,
            )
            session.add(sale)
            session.flush()

            for item_data in sale_items_records:
                si = SaleItem(
                    sale_id=sale.id,
                    medicine_id=item_data["medicine_id"],
                    batch_id=item_data["batch_id"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                    purchase_price=item_data["purchase_price"],
                    subtotal=item_data["subtotal"],
                )
                session.add(si)

            sale_id = sale.id
            c_name = customer_obj.name if customer_obj else "Walk-in Customer"

        # Rule 9: Audit log entry
        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "cashier"),
            action="CREATE",
            module="BILLING",
            description=f"Generated invoice '{invoice_no}' for '{c_name}' (Total: ₹{grand_total:.2f}, Payment: {payment_method})",
        )

        return {
            "id": sale_id,
            "invoice_no": invoice_no,
            "customer_name": c_name,
            "customer_phone": customer_obj.phone if customer_obj else "-",
            "doctor_name": prescription_obj.doctor_name if prescription_obj else "-",
            "pharmacist_name": current_user.get("full_name", current_user.get("username", "Pharmacist")),
            "payment_method": payment_method,
            "sale_date": now_dt.strftime("%Y-%m-%d %H:%M"),
            "subtotal": subtotal,
            "discount": discount_amount,
            "tax": tax_amount,
            "total_amount": grand_total,
            "profit": round(total_profit, 2),
            "items": sale_items_records,
        }

    @staticmethod
    def list_sales(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        payment_method: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List sales transactions with customer names and dispensed item counts."""
        with get_db() as session:
            stmt = (
                select(
                    Sale,
                    Customer.name.label("customer_name"),
                    User.full_name.label("pharmacist_name"),
                    func.count(SaleItem.id).label("item_count"),
                )
                .outerjoin(Customer, Sale.customer_id == Customer.id)
                .join(User, Sale.user_id == User.id)
                .outerjoin(SaleItem, Sale.id == SaleItem.sale_id)
                .group_by(Sale.id)
                .order_by(desc(Sale.sale_date), desc(Sale.id))
            )

            if customer_id:
                stmt = stmt.where(Sale.customer_id == customer_id)

            if payment_method and payment_method != "All":
                stmt = stmt.where(Sale.payment_method == payment_method)

            if search:
                term = f"%{search.strip().lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Sale.invoice_no).like(term),
                        func.lower(Customer.name).like(term),
                    )
                )

            stmt = stmt.limit(limit)
            rows = session.execute(stmt).all()

            sales = []
            for s, c_name, p_name, it_count in rows:
                sales.append({
                    "id": s.id,
                    "invoice_no": s.invoice_no,
                    "customer_name": c_name or "Walk-in Retail",
                    "pharmacist_name": p_name,
                    "sale_date": s.sale_date.strftime("%Y-%m-%d %H:%M") if s.sale_date else "",
                    "payment_method": s.payment_method,
                    "subtotal": round(s.subtotal, 2),
                    "discount": round(s.discount, 2),
                    "tax": round(s.tax, 2),
                    "total_amount": round(s.total_amount, 2),
                    "item_count": it_count,
                    "notes": s.notes or "-",
                })
            return sales

    @staticmethod
    def get_sale(sale_id: int) -> Dict[str, Any]:
        """Fetch complete sale invoice details, items, batches, and profit margin."""
        with get_db() as session:
            s = session.get(Sale, sale_id)
            if not s:
                raise NotFoundException(f"Sales invoice #{sale_id} not found.")

            c_name = s.customer.name if s.customer else "Walk-in Customer"
            c_phone = s.customer.phone if s.customer else "-"
            doctor_name = s.prescription.doctor_name if s.prescription else "-"
            pharmacist_name = s.pharmacist_user.full_name if s.pharmacist_user else "Pharmacist"

            items = []
            total_profit = 0.0
            for it in s.items:
                med_name = it.medicine.name if it.medicine else "Medicine"
                strength = it.medicine.strength if it.medicine else ""
                batch_no = it.batch.batch_no if it.batch else "Batch"
                exp_date = it.batch.expiry_date.strftime("%Y-%m-%d") if it.batch else "-"

                line_profit = (it.unit_price - it.purchase_price) * it.quantity
                total_profit += line_profit

                items.append({
                    "id": it.id,
                    "medicine_id": it.medicine_id,
                    "medicine_name": f"{med_name} ({strength})",
                    "batch_id": it.batch_id,
                    "batch_no": batch_no,
                    "expiry_date": exp_date,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "purchase_price": it.purchase_price,
                    "subtotal": it.subtotal,
                    "profit": round(line_profit, 2),
                })

            return {
                "id": s.id,
                "invoice_no": s.invoice_no,
                "customer_name": c_name,
                "customer_phone": c_phone,
                "doctor_name": doctor_name,
                "pharmacist_name": pharmacist_name,
                "sale_date": s.sale_date.strftime("%Y-%m-%d %H:%M") if s.sale_date else "",
                "payment_method": s.payment_method,
                "subtotal": round(s.subtotal, 2),
                "discount": round(s.discount, 2),
                "tax": round(s.tax, 2),
                "total_amount": round(s.total_amount, 2),
                "profit": round(total_profit, 2),
                "notes": s.notes or "",
                "items": items,
            }
