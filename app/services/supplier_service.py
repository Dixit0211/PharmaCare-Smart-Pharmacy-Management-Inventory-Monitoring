"""Supplier and wholesale distributor management service."""

from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    ConflictException,
)
from app.models.supplier import Supplier
from app.models.purchase import Purchase
from app.services.audit_service import AuditService
from app.utils.validators import validate_phone_number, validate_email_format
from app.core.logging import get_logger

logger = get_logger(__name__)


class SupplierService:
    """Business logic for pharmaceutical suppliers and wholesale vendors."""

    @staticmethod
    def list_suppliers(search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all suppliers with procurement volume and purchase order counts."""
        with get_db() as session:
            stmt = (
                select(
                    Supplier,
                    func.count(Purchase.id).label("purchase_count"),
                    func.coalesce(func.sum(Purchase.total_amount), 0.0).label("total_procured"),
                )
                .outerjoin(Purchase, Supplier.id == Purchase.supplier_id)
                .group_by(Supplier.id)
                .order_by(Supplier.name.asc())
            )

            if search:
                term = f"%{search.strip().lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Supplier.name).like(term),
                        func.lower(Supplier.contact_person).like(term),
                        func.lower(Supplier.phone).like(term),
                        func.lower(Supplier.email).like(term),
                        func.lower(Supplier.gst_number).like(term),
                    )
                )

            rows = session.execute(stmt).all()

            suppliers = []
            for sup, p_count, total_spend in rows:
                suppliers.append({
                    "id": sup.id,
                    "name": sup.name,
                    "contact_person": sup.contact_person or "-",
                    "phone": sup.phone,
                    "email": sup.email or "-",
                    "address": sup.address or "-",
                    "gst_number": sup.gst_number or "-",
                    "purchase_count": p_count,
                    "total_procured": round(float(total_spend), 2),
                    "created_at": sup.created_at.strftime("%Y-%m-%d") if sup.created_at else "",
                })
            return suppliers

    @staticmethod
    def get_supplier(supplier_id: int) -> Dict[str, Any]:
        """Fetch supplier profile and recent purchase orders."""
        with get_db() as session:
            sup = session.get(Supplier, supplier_id)
            if not sup:
                raise NotFoundException(f"Supplier with ID {supplier_id} not found.")

            purchases = [
                {
                    "id": p.id,
                    "invoice_no": p.invoice_no,
                    "purchase_date": p.purchase_date.strftime("%Y-%m-%d"),
                    "total_amount": p.total_amount,
                    "status": p.status,
                }
                for p in sorted(sup.purchases, key=lambda x: x.purchase_date, reverse=True)
            ]

            return {
                "id": sup.id,
                "name": sup.name,
                "contact_person": sup.contact_person or "",
                "phone": sup.phone,
                "email": sup.email or "",
                "address": sup.address or "",
                "gst_number": sup.gst_number or "",
                "purchases": purchases,
            }

    @staticmethod
    def create_supplier(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new wholesale supplier record with validation."""
        name = (data.get("name") or "").strip()
        contact_person = (data.get("contact_person") or "").strip() or None
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip() or None
        address = (data.get("address") or "").strip() or None
        gst_number = (data.get("gst_number") or "").strip().upper() or None

        if not name:
            raise ValidationError("Supplier name is required.")

        is_phone_valid, phone_err = validate_phone_number(phone)
        if not is_phone_valid:
            raise ValidationError(phone_err)

        if email:
            is_email_valid, email_err = validate_email_format(email)
            if not is_email_valid:
                raise ValidationError(email_err)

        with get_db() as session:
            existing = session.scalars(
                select(Supplier).where(func.lower(Supplier.name) == name.lower())
            ).first()
            if existing:
                raise ConflictException(f"Supplier '{name}' is already registered.")

            sup = Supplier(
                name=name,
                contact_person=contact_person,
                phone=phone,
                email=email,
                address=address,
                gst_number=gst_number,
            )
            session.add(sup)
            session.flush()
            sup_id = sup.id

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CREATE",
            module="SUPPLIER",
            description=f"Registered new supplier '{name}' (Phone: {phone})",
        )

        return {"id": sup_id, "name": name, "phone": phone}

    @staticmethod
    def update_supplier(current_user: Dict[str, Any], supplier_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update supplier profile."""
        name = (data.get("name") or "").strip()
        contact_person = (data.get("contact_person") or "").strip() or None
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip() or None
        address = (data.get("address") or "").strip() or None
        gst_number = (data.get("gst_number") or "").strip().upper() or None

        if not name:
            raise ValidationError("Supplier name is required.")

        is_phone_valid, phone_err = validate_phone_number(phone)
        if not is_phone_valid:
            raise ValidationError(phone_err)

        if email:
            is_email_valid, email_err = validate_email_format(email)
            if not is_email_valid:
                raise ValidationError(email_err)

        with get_db() as session:
            sup = session.get(Supplier, supplier_id)
            if not sup:
                raise NotFoundException(f"Supplier with ID {supplier_id} not found.")

            if sup.name.lower() != name.lower():
                existing = session.scalars(
                    select(Supplier).where(
                        (func.lower(Supplier.name) == name.lower()) & (Supplier.id != supplier_id)
                    )
                ).first()
                if existing:
                    raise ConflictException(f"Supplier '{name}' already exists.")

            old_name = sup.name
            sup.name = name
            sup.contact_person = contact_person
            sup.phone = phone
            sup.email = email
            sup.address = address
            sup.gst_number = gst_number

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="UPDATE",
            module="SUPPLIER",
            description=f"Updated supplier details for '{old_name}' -> '{name}'",
        )

        return {"id": supplier_id, "name": name}

    @staticmethod
    def delete_supplier(current_user: Dict[str, Any], supplier_id: int) -> None:
        """Delete supplier only if no purchase orders exist."""
        with get_db() as session:
            sup = session.get(Supplier, supplier_id)
            if not sup:
                raise NotFoundException(f"Supplier with ID {supplier_id} not found.")

            # Rule 7: Suppliers in use cannot be deleted
            purchase_count = session.scalars(
                select(func.count(Purchase.id)).where(Purchase.supplier_id == supplier_id)
            ).one()

            if purchase_count > 0:
                raise ConflictException(
                    f"Cannot delete supplier '{sup.name}' because {purchase_count} purchase invoice(s) are recorded under this supplier. Historical procurement records must be preserved."
                )

            sup_name = sup.name
            session.delete(sup)

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="DELETE",
            module="SUPPLIER",
            description=f"Deleted supplier '{sup_name}'",
        )
