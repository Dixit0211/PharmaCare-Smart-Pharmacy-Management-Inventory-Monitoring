"""Medicine master catalog service."""

from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    ConflictException,
)
from app.models.medicine import Medicine, MedicineBatch
from app.models.category import Category
from app.models.sale import SaleItem
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class MedicineService:
    """Business logic for master medicine records and catalog queries."""

    @staticmethod
    def list_medicines(
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        status: Optional[str] = None,
        prescription_required: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        List medicines with live computed stock from non-expired batches.
        Stock = sum(MedicineBatch.quantity where expiry_date >= today).
        """
        today = date.today()

        with get_db() as session:
            stmt = (
                select(
                    Medicine,
                    Category.name.label("category_name"),
                )
                .join(Category, Medicine.category_id == Category.id)
                .order_by(Medicine.name.asc())
            )

            if search:
                term = f"%{search.strip().lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Medicine.name).like(term),
                        func.lower(Medicine.generic_name).like(term),
                        func.lower(Medicine.brand).like(term),
                        func.lower(Medicine.barcode).like(term),
                        func.lower(Medicine.manufacturer).like(term),
                    )
                )

            if category_id:
                stmt = stmt.where(Medicine.category_id == category_id)

            if status and status != "All":
                stmt = stmt.where(Medicine.status == status.lower())

            if prescription_required is not None:
                stmt = stmt.where(Medicine.prescription_required == prescription_required)

            rows = session.execute(stmt).all()

            # For each medicine, calculate current stock and batch metrics
            medicines_data = []
            for med, cat_name in rows:
                batches = med.batches

                total_stock = 0
                expired_stock = 0
                active_batches_count = 0
                near_expiry_batches_count = 0

                for b in batches:
                    if b.expiry_date >= today:
                        total_stock += b.quantity
                        if b.quantity > 0:
                            active_batches_count += 1
                        days_left = (b.expiry_date - today).days
                        if 0 <= days_left <= 30 and b.quantity > 0:
                            near_expiry_batches_count += 1
                    else:
                        expired_stock += b.quantity

                is_low_stock = total_stock <= med.min_stock

                medicines_data.append({
                    "id": med.id,
                    "name": med.name,
                    "generic_name": med.generic_name,
                    "brand": med.brand or "-",
                    "category_id": med.category_id,
                    "category_name": cat_name,
                    "manufacturer": med.manufacturer or "-",
                    "barcode": med.barcode or "-",
                    "dosage_form": med.dosage_form,
                    "strength": med.strength,
                    "selling_price": med.selling_price,
                    "min_stock": med.min_stock,
                    "prescription_required": med.prescription_required,
                    "status": med.status,
                    "total_stock": total_stock,
                    "expired_stock": expired_stock,
                    "active_batches_count": active_batches_count,
                    "near_expiry_batches_count": near_expiry_batches_count,
                    "is_low_stock": is_low_stock,
                    "created_at": med.created_at.strftime("%Y-%m-%d") if med.created_at else "",
                })

            return medicines_data

    @staticmethod
    def get_medicine(medicine_id: int) -> Dict[str, Any]:
        """Retrieve medicine with all associated batches and stock calculation."""
        today = date.today()

        with get_db() as session:
            med = session.get(Medicine, medicine_id)
            if not med:
                raise NotFoundException(f"Medicine with ID {medicine_id} not found.")

            category_name = med.category.name if med.category else "Uncategorized"

            batches_list = []
            total_stock = 0
            for b in med.batches:
                days_left = (b.expiry_date - today).days
                if b.expiry_date < today:
                    b_status = "expired"
                elif days_left <= 30:
                    b_status = "expiring_soon"
                else:
                    b_status = "safe"

                if b.expiry_date >= today:
                    total_stock += b.quantity

                batches_list.append({
                    "id": b.id,
                    "batch_no": b.batch_no,
                    "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
                    "days_remaining": days_left,
                    "quantity": b.quantity,
                    "purchase_price": b.purchase_price,
                    "status": b_status,
                })

            return {
                "id": med.id,
                "name": med.name,
                "generic_name": med.generic_name,
                "brand": med.brand or "",
                "category_id": med.category_id,
                "category_name": category_name,
                "manufacturer": med.manufacturer or "",
                "barcode": med.barcode or "",
                "dosage_form": med.dosage_form,
                "strength": med.strength,
                "selling_price": med.selling_price,
                "min_stock": med.min_stock,
                "prescription_required": med.prescription_required,
                "status": med.status,
                "total_stock": total_stock,
                "is_low_stock": total_stock <= med.min_stock,
                "batches": batches_list,
            }

    @staticmethod
    def create_medicine(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new medicine master record."""
        name = (data.get("name") or "").strip()
        generic_name = (data.get("generic_name") or "").strip()
        category_id = data.get("category_id")
        strength = (data.get("strength") or "").strip()
        dosage_form = (data.get("dosage_form") or "Tablet").strip()
        selling_price = float(data.get("selling_price", 0.0))
        min_stock = int(data.get("min_stock", 15))
        barcode = (data.get("barcode") or "").strip() or None
        manufacturer = (data.get("manufacturer") or "").strip() or None
        brand = (data.get("brand") or "").strip() or None
        prescription_required = bool(data.get("prescription_required", False))

        if not name or not generic_name or not category_id or not strength:
            raise ValidationError("Name, generic name, category, and strength are mandatory fields.")

        if selling_price < 0:
            raise ValidationError("Selling price cannot be negative.")

        if min_stock < 0:
            raise ValidationError("Minimum stock threshold cannot be negative.")

        with get_db() as session:
            # Verify category exists
            cat = session.get(Category, category_id)
            if not cat:
                raise ValidationError("Specified category does not exist.")

            # Check barcode uniqueness if provided
            if barcode:
                existing_bc = session.scalars(
                    select(Medicine).where(Medicine.barcode == barcode)
                ).first()
                if existing_bc:
                    raise ConflictException(f"Barcode '{barcode}' is already assigned to {existing_bc.name}.")

            # Check duplicate medicine
            existing_med = session.scalars(
                select(Medicine).where(
                    (func.lower(Medicine.name) == name.lower())
                    & (func.lower(Medicine.strength) == strength.lower())
                )
            ).first()
            if existing_med:
                raise ConflictException(f"Medicine '{name} ({strength})' already exists in the catalog.")

            med = Medicine(
                name=name,
                generic_name=generic_name,
                brand=brand,
                category_id=category_id,
                manufacturer=manufacturer,
                barcode=barcode,
                dosage_form=dosage_form,
                strength=strength,
                selling_price=selling_price,
                min_stock=min_stock,
                prescription_required=prescription_required,
                status="active",
            )
            session.add(med)
            session.flush()
            new_id = med.id

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CREATE",
            module="MEDICINE",
            description=f"Added new medicine '{name} {strength}' (Price: ₹{selling_price:.2f})",
        )

        return {"id": new_id, "name": name, "strength": strength}

    @staticmethod
    def update_medicine(current_user: Dict[str, Any], medicine_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing medicine master record."""
        name = (data.get("name") or "").strip()
        generic_name = (data.get("generic_name") or "").strip()
        category_id = data.get("category_id")
        strength = (data.get("strength") or "").strip()
        dosage_form = (data.get("dosage_form") or "Tablet").strip()
        selling_price = float(data.get("selling_price", 0.0))
        min_stock = int(data.get("min_stock", 15))
        barcode = (data.get("barcode") or "").strip() or None
        manufacturer = (data.get("manufacturer") or "").strip() or None
        brand = (data.get("brand") or "").strip() or None
        prescription_required = bool(data.get("prescription_required", False))
        status = data.get("status", "active")

        if not name or not generic_name or not category_id or not strength:
            raise ValidationError("Name, generic name, category, and strength are mandatory fields.")

        if selling_price < 0:
            raise ValidationError("Selling price cannot be negative.")

        if min_stock < 0:
            raise ValidationError("Minimum stock threshold cannot be negative.")

        with get_db() as session:
            med = session.get(Medicine, medicine_id)
            if not med:
                raise NotFoundException(f"Medicine with ID {medicine_id} not found.")

            # Check barcode uniqueness
            if barcode and barcode != med.barcode:
                existing_bc = session.scalars(
                    select(Medicine).where((Medicine.barcode == barcode) & (Medicine.id != medicine_id))
                ).first()
                if existing_bc:
                    raise ConflictException(f"Barcode '{barcode}' is already assigned to {existing_bc.name}.")

            med.name = name
            med.generic_name = generic_name
            med.brand = brand
            med.category_id = category_id
            med.manufacturer = manufacturer
            med.barcode = barcode
            med.dosage_form = dosage_form
            med.strength = strength
            med.selling_price = selling_price
            med.min_stock = min_stock
            med.prescription_required = prescription_required
            med.status = status

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="UPDATE",
            module="MEDICINE",
            description=f"Updated medicine '{name} {strength}' (ID: {medicine_id})",
        )

        return {"id": medicine_id, "name": name, "strength": strength}

    @staticmethod
    def delete_medicine(current_user: Dict[str, Any], medicine_id: int) -> None:
        """Deactivate or delete medicine based on transaction history."""
        with get_db() as session:
            med = session.get(Medicine, medicine_id)
            if not med:
                raise NotFoundException(f"Medicine with ID {medicine_id} not found.")

            # Check if there are sales records
            sales_count = session.scalars(
                select(func.count(SaleItem.id)).where(SaleItem.medicine_id == medicine_id)
            ).one()

            med_name = med.name
            if sales_count > 0:
                # Soft deactivate to protect historical audit trail and billing reports
                med.status = "inactive"
                action_desc = f"Deactivated medicine '{med_name}' (Preserving {sales_count} sales records)"
            else:
                session.delete(med)
                action_desc = f"Deleted medicine '{med_name}' from catalog"

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="DELETE",
            module="MEDICINE",
            description=action_desc,
        )
