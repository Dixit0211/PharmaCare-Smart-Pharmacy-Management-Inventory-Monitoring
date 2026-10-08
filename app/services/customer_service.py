"""Customer and patient profiles management service."""

from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    ConflictException,
)
from app.models.customer import Customer
from app.models.sale import Sale
from app.models.prescription import Prescription
from app.services.audit_service import AuditService
from app.utils.validators import validate_phone_number, validate_email_format
from app.core.logging import get_logger

logger = get_logger(__name__)


class CustomerService:
    """Business logic for customer/patient profiles and prescription history."""

    @staticmethod
    def list_customers(search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all customer profiles with order counts and total spending."""
        with get_db() as session:
            stmt = (
                select(
                    Customer,
                    func.count(func.distinct(Sale.id)).label("sale_count"),
                    func.coalesce(func.sum(Sale.total_amount), 0.0).label("total_spent"),
                    func.count(func.distinct(Prescription.id)).label("rx_count"),
                )
                .outerjoin(Sale, Customer.id == Sale.customer_id)
                .outerjoin(Prescription, Customer.id == Prescription.customer_id)
                .group_by(Customer.id)
                .order_by(Customer.name.asc())
            )

            if search:
                term = f"%{search.strip().lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Customer.name).like(term),
                        func.lower(Customer.phone).like(term),
                        func.lower(Customer.email).like(term),
                    )
                )

            rows = session.execute(stmt).all()

            customers = []
            for cust, s_count, spent, rx_c in rows:
                customers.append({
                    "id": cust.id,
                    "name": cust.name,
                    "phone": cust.phone,
                    "email": cust.email or "-",
                    "address": cust.address or "-",
                    "sale_count": s_count,
                    "total_spent": round(float(spent), 2),
                    "rx_count": rx_c,
                    "created_at": cust.created_at.strftime("%Y-%m-%d") if cust.created_at else "",
                })
            return customers

    @staticmethod
    def get_customer(customer_id: int) -> Dict[str, Any]:
        """Fetch customer profile, sales invoices, and registered prescriptions."""
        with get_db() as session:
            cust = session.get(Customer, customer_id)
            if not cust:
                raise NotFoundException(f"Customer with ID {customer_id} not found.")

            sales = [
                {
                    "id": s.id,
                    "invoice_no": s.invoice_no,
                    "sale_date": s.sale_date.strftime("%Y-%m-%d %H:%M"),
                    "total_amount": round(s.total_amount, 2),
                    "payment_method": s.payment_method,
                }
                for s in sorted(cust.sales, key=lambda x: x.sale_date, reverse=True)
            ]

            prescriptions = [
                {
                    "id": rx.id,
                    "doctor_name": rx.doctor_name,
                    "patient_name": rx.patient_name,
                    "date": rx.prescription_date.strftime("%Y-%m-%d"),
                    "diagnosis": rx.diagnosis or "-",
                }
                for rx in sorted(cust.prescriptions, key=lambda x: x.prescription_date, reverse=True)
            ]

            return {
                "id": cust.id,
                "name": cust.name,
                "phone": cust.phone,
                "email": cust.email or "",
                "address": cust.address or "",
                "sales": sales,
                "prescriptions": prescriptions,
                "total_spent": round(sum(s["total_amount"] for s in sales), 2),
            }

    @staticmethod
    def create_customer(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new patient/customer record with validation."""
        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip() or None
        address = (data.get("address") or "").strip() or None

        if not name:
            raise ValidationError("Customer name is required.")

        is_phone_valid, phone_err = validate_phone_number(phone)
        if not is_phone_valid:
            raise ValidationError(phone_err)

        if email:
            is_email_valid, email_err = validate_email_format(email)
            if not is_email_valid:
                raise ValidationError(email_err)

        with get_db() as session:
            # Check unique phone
            existing = session.scalars(
                select(Customer).where(Customer.phone == phone)
            ).first()
            if existing:
                raise ConflictException(f"Customer with phone '{phone}' is already registered as '{existing.name}'.")

            cust = Customer(name=name, phone=phone, email=email, address=address)
            session.add(cust)
            session.flush()
            cust_id = cust.id

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CREATE",
            module="CUSTOMER",
            description=f"Created customer profile '{name}' (Phone: {phone})",
        )

        return {"id": cust_id, "name": name, "phone": phone}

    @staticmethod
    def update_customer(current_user: Dict[str, Any], customer_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update customer profile."""
        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip() or None
        address = (data.get("address") or "").strip() or None

        if not name:
            raise ValidationError("Customer name is required.")

        is_phone_valid, phone_err = validate_phone_number(phone)
        if not is_phone_valid:
            raise ValidationError(phone_err)

        if email:
            is_email_valid, email_err = validate_email_format(email)
            if not is_email_valid:
                raise ValidationError(email_err)

        with get_db() as session:
            cust = session.get(Customer, customer_id)
            if not cust:
                raise NotFoundException(f"Customer with ID {customer_id} not found.")

            if cust.phone != phone:
                existing = session.scalars(
                    select(Customer).where((Customer.phone == phone) & (Customer.id != customer_id))
                ).first()
                if existing:
                    raise ConflictException(f"Phone '{phone}' is already registered to {existing.name}.")

            old_name = cust.name
            cust.name = name
            cust.phone = phone
            cust.email = email
            cust.address = address

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="UPDATE",
            module="CUSTOMER",
            description=f"Updated customer profile '{old_name}' -> '{name}'",
        )

        return {"id": customer_id, "name": name, "phone": phone}

    @staticmethod
    def delete_customer(current_user: Dict[str, Any], customer_id: int) -> None:
        """Delete customer record if no sales invoices exist."""
        with get_db() as session:
            cust = session.get(Customer, customer_id)
            if not cust:
                raise NotFoundException(f"Customer with ID {customer_id} not found.")

            sales_count = session.scalars(
                select(func.count(Sale.id)).where(Sale.customer_id == customer_id)
            ).one()

            if sales_count > 0:
                raise ConflictException(
                    f"Cannot delete customer '{cust.name}' because {sales_count} sales invoice(s) are linked to their account. Historical billing records must be preserved."
                )

            cust_name = cust.name
            session.delete(cust)

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="DELETE",
            module="CUSTOMER",
            description=f"Deleted customer '{cust_name}'",
        )
