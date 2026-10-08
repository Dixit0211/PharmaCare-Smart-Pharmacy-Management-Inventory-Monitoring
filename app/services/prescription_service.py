"""Medical prescription compliance and validation service."""

from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, desc, or_
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    ConflictException,
)
from app.models.prescription import Prescription
from app.models.customer import Customer
from app.models.sale import Sale
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class PrescriptionService:
    """Business logic for doctor prescriptions and statutory compliance tracking."""

    @staticmethod
    def list_prescriptions(
        customer_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List doctor prescriptions with patient and customer references."""
        with get_db() as session:
            stmt = (
                select(
                    Prescription,
                    Customer.name.label("customer_name"),
                    Customer.phone.label("customer_phone"),
                    func.count(Sale.id).label("sales_count"),
                )
                .outerjoin(Customer, Prescription.customer_id == Customer.id)
                .outerjoin(Sale, Prescription.id == Sale.prescription_id)
                .group_by(Prescription.id)
                .order_by(desc(Prescription.prescription_date), desc(Prescription.id))
            )

            if customer_id:
                stmt = stmt.where(Prescription.customer_id == customer_id)

            if search:
                term = f"%{search.strip().lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Prescription.patient_name).like(term),
                        func.lower(Prescription.doctor_name).like(term),
                        func.lower(Prescription.doctor_reg_no).like(term),
                        func.lower(Customer.name).like(term),
                        func.lower(Customer.phone).like(term),
                    )
                )

            rows = session.execute(stmt).all()

            prescriptions = []
            for rx, c_name, c_phone, s_count in rows:
                prescriptions.append({
                    "id": rx.id,
                    "customer_id": rx.customer_id,
                    "customer_name": c_name or "-",
                    "customer_phone": c_phone or "-",
                    "doctor_name": rx.doctor_name,
                    "doctor_reg_no": rx.doctor_reg_no or "-",
                    "patient_name": rx.patient_name,
                    "patient_age": rx.patient_age,
                    "patient_gender": rx.patient_gender or "-",
                    "prescription_date": rx.prescription_date.strftime("%Y-%m-%d"),
                    "diagnosis": rx.diagnosis or "-",
                    "notes": rx.notes or "-",
                    "file_path": rx.file_path,
                    "sales_count": s_count,
                    "created_at": rx.created_at.strftime("%Y-%m-%d") if rx.created_at else "",
                })
            return prescriptions

    @staticmethod
    def get_prescription(prescription_id: int) -> Dict[str, Any]:
        """Fetch prescription details and linked sales."""
        with get_db() as session:
            rx = session.get(Prescription, prescription_id)
            if not rx:
                raise NotFoundException(f"Prescription with ID {prescription_id} not found.")

            c_name = rx.customer.name if rx.customer else None
            c_phone = rx.customer.phone if rx.customer else None

            sales = [
                {
                    "id": s.id,
                    "invoice_no": s.invoice_no,
                    "sale_date": s.sale_date.strftime("%Y-%m-%d %H:%M"),
                    "total_amount": round(s.total_amount, 2),
                }
                for s in rx.sales
            ]

            return {
                "id": rx.id,
                "customer_id": rx.customer_id,
                "customer_name": c_name,
                "customer_phone": c_phone,
                "doctor_name": rx.doctor_name,
                "doctor_reg_no": rx.doctor_reg_no,
                "patient_name": rx.patient_name,
                "patient_age": rx.patient_age,
                "patient_gender": rx.patient_gender,
                "prescription_date": rx.prescription_date,
                "diagnosis": rx.diagnosis or "",
                "notes": rx.notes or "",
                "file_path": rx.file_path,
                "sales": sales,
            }

    @staticmethod
    def create_prescription(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new prescription record."""
        doctor_name = (data.get("doctor_name") or "").strip()
        doctor_reg_no = (data.get("doctor_reg_no") or "").strip() or None
        patient_name = (data.get("patient_name") or "").strip()
        patient_age = data.get("patient_age")
        patient_gender = data.get("patient_gender")
        rx_date = data.get("prescription_date") or date.today()
        diagnosis = (data.get("diagnosis") or "").strip() or None
        notes = (data.get("notes") or "").strip() or None
        customer_id = data.get("customer_id")
        file_path = data.get("file_path")

        if not doctor_name:
            raise ValidationError("Doctor name is required.")

        if not patient_name:
            raise ValidationError("Patient name is required.")

        if isinstance(rx_date, str):
            rx_date = date.fromisoformat(rx_date)

        with get_db() as session:
            if customer_id:
                cust = session.get(Customer, customer_id)
                if not cust:
                    raise ValidationError("Referenced customer does not exist.")

            rx = Prescription(
                customer_id=customer_id,
                doctor_name=doctor_name,
                doctor_reg_no=doctor_reg_no,
                patient_name=patient_name,
                patient_age=patient_age,
                patient_gender=patient_gender,
                prescription_date=rx_date,
                diagnosis=diagnosis,
                notes=notes,
                file_path=file_path,
            )
            session.add(rx)
            session.flush()
            rx_id = rx.id

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CREATE",
            module="PRESCRIPTION",
            description=f"Logged prescription from '{doctor_name}' for patient '{patient_name}'",
        )

        return {"id": rx_id, "doctor_name": doctor_name, "patient_name": patient_name}

    @staticmethod
    def update_prescription(current_user: Dict[str, Any], prescription_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing prescription."""
        doctor_name = (data.get("doctor_name") or "").strip()
        patient_name = (data.get("patient_name") or "").strip()

        if not doctor_name or not patient_name:
            raise ValidationError("Doctor name and patient name are required.")

        rx_date = data.get("prescription_date") or date.today()
        if isinstance(rx_date, str):
            rx_date = date.fromisoformat(rx_date)

        with get_db() as session:
            rx = session.get(Prescription, prescription_id)
            if not rx:
                raise NotFoundException(f"Prescription with ID {prescription_id} not found.")

            rx.doctor_name = doctor_name
            rx.doctor_reg_no = (data.get("doctor_reg_no") or "").strip() or None
            rx.patient_name = patient_name
            rx.patient_age = data.get("patient_age")
            rx.patient_gender = data.get("patient_gender")
            rx.prescription_date = rx_date
            rx.diagnosis = (data.get("diagnosis") or "").strip() or None
            rx.notes = (data.get("notes") or "").strip() or None
            rx.customer_id = data.get("customer_id")

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="UPDATE",
            module="PRESCRIPTION",
            description=f"Updated prescription #{prescription_id} for '{patient_name}'",
        )

        return {"id": prescription_id, "doctor_name": doctor_name, "patient_name": patient_name}

    @staticmethod
    def delete_prescription(current_user: Dict[str, Any], prescription_id: int) -> None:
        """Delete prescription if not linked to existing sales."""
        with get_db() as session:
            rx = session.get(Prescription, prescription_id)
            if not rx:
                raise NotFoundException(f"Prescription with ID {prescription_id} not found.")

            sales_count = session.scalars(
                select(func.count(Sale.id)).where(Sale.prescription_id == prescription_id)
            ).one()

            if sales_count > 0:
                raise ConflictException(
                    f"Cannot delete prescription #{prescription_id} because {sales_count} sale(s) have been dispensed under this prescription."
                )

            p_name = rx.patient_name
            session.delete(rx)

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="DELETE",
            module="PRESCRIPTION",
            description=f"Deleted prescription #{prescription_id} (Patient: {p_name})",
        )
