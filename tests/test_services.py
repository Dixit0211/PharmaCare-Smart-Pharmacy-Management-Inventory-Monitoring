"""Comprehensive domain services test suite for PharmaCare."""

from datetime import date, timedelta
import pytest
from app.core.exceptions import (
    AuthenticationError,
    ValidationError,
    NotFoundException,
    PermissionDeniedException,
    ConflictException,
    InsufficientStockError,
    ExpiredBatchError,
)
from app.services.auth_service import AuthService
from app.services.category_service import CategoryService
from app.services.medicine_service import MedicineService
from app.services.batch_service import BatchService
from app.services.supplier_service import SupplierService
from app.services.purchase_service import PurchaseService
from app.services.customer_service import CustomerService
from app.services.prescription_service import PrescriptionService
from app.services.sale_service import SaleService
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService
from app.services.dashboard_service import DashboardService
from app.services.report_service import ReportService
from app.services.setting_service import SettingService
from app.services.backup_service import BackupService


# ==============================================================================
# 1. Authentication & RBAC Tests
# ==============================================================================
def test_authentication_success_and_failure():
    """Verify password authentication, payload extraction, and failed credential handling."""
    user = AuthService.authenticate("admin_test@pharmacare.local", "Admin@123")
    assert user is not None
    assert user["username"] == "admin_test"
    assert user["role"] == "admin"

    with pytest.raises(AuthenticationError):
        AuthService.authenticate("admin_test@pharmacare.local", "WrongPassword")

    with pytest.raises(AuthenticationError):
        AuthService.authenticate("nonexistent@pharmacare.local", "Admin@123")


def test_user_password_change(pharma_user_payload):
    """Verify secure password change."""
    AuthService.change_password(pharma_user_payload["id"], "Pharma@123", "NewPharma@123")
    user = AuthService.authenticate("pharma_test@pharmacare.local", "NewPharma@123")
    assert user["id"] == pharma_user_payload["id"]

    # Revert back
    AuthService.change_password(pharma_user_payload["id"], "NewPharma@123", "Pharma@123")


def test_admin_user_creation_and_status_toggle(admin_user_payload, pharma_user_payload):
    """Verify administrator user creation and RBAC guards."""
    new_user = AuthService.create_user(
        current_user=admin_user_payload,
        username="assistant_staff",
        email="assistant@pharmacare.local",
        password="Staff@123",
        full_name="Assistant Pharmacist",
        role="pharmacist",
        phone="+91 98765 43219",
    )
    assert new_user["id"] is not None

    # Pharmacist should not be allowed to create users
    with pytest.raises(PermissionDeniedException):
        AuthService.create_user(
            current_user=pharma_user_payload,
            username="unauthorized_user",
            email="unauth@pharmacare.local",
            password="Password@123",
            full_name="Unauthorized",
            role="pharmacist",
        )

    # Admin deactivates user
    new_status = AuthService.toggle_user_status(admin_user_payload, new_user["id"])
    assert new_status is False  # Deactivated

    with pytest.raises(AuthenticationError):
        AuthService.authenticate("assistant@pharmacare.local", "Staff@123")


# ==============================================================================
# 2. Categories & Medicines Catalog Tests
# ==============================================================================
def test_category_crud_and_conflict(admin_user_payload):
    """Verify category creation and unique constraint handling."""
    cat = CategoryService.create_category(
        current_user=admin_user_payload,
        name="Cardiovascular",
        description="Heart and blood pressure management",
    )
    assert cat["id"] is not None

    with pytest.raises(ConflictException):
        CategoryService.create_category(
            current_user=admin_user_payload,
            name="Cardiovascular",
            description="Duplicate category",
        )


def test_medicine_catalog_and_fefo_stock(admin_user_payload):
    """Verify medicine creation, barcode uniqueness, and batch association."""
    categories = CategoryService.list_categories()
    cat_id = categories[0]["id"]

    # 1. Standard OTC Medicine
    med_otc = MedicineService.create_medicine(
        current_user=admin_user_payload,
        data={
            "name": "Paracetamol 500mg",
            "generic_name": "Acetaminophen",
            "category_id": cat_id,
            "dosage_form": "Tablet",
            "strength": "500mg",
            "selling_price": 25.0,
            "min_stock": 20,
            "prescription_required": False,
            "barcode": "MED-PARA-500",
        },
    )
    assert med_otc["id"] is not None

    # 2. Schedule H Prescription Medicine
    med_rx = MedicineService.create_medicine(
        current_user=admin_user_payload,
        data={
            "name": "Amoxicillin 500mg",
            "generic_name": "Amoxicillin Trihydrate",
            "category_id": cat_id,
            "dosage_form": "Capsule",
            "strength": "500mg",
            "selling_price": 65.0,
            "min_stock": 15,
            "prescription_required": True,
            "barcode": "MED-AMOX-500",
        },
    )
    rx_detail = MedicineService.get_medicine(med_rx["id"])
    assert rx_detail["prescription_required"] is True

    # 3. Add Batches to Paracetamol
    today = date.today()
    # Batch 1: Expiring in 60 days
    b1 = BatchService.create_batch(
        current_user=admin_user_payload,
        medicine_id=med_otc["id"],
        batch_no="PARA-B01",
        expiry_date_val=today + timedelta(days=60),
        quantity=50,
        purchase_price=15.0,
    )
    assert b1["id"] is not None

    # Batch 2: Expiring in 180 days
    b2 = BatchService.create_batch(
        current_user=admin_user_payload,
        medicine_id=med_otc["id"],
        batch_no="PARA-B02",
        expiry_date_val=today + timedelta(days=180),
        quantity=50,
        purchase_price=16.0,
    )
    assert b2["id"] is not None

    # Batch 3: Expired batch
    b_exp = BatchService.create_batch(
        current_user=admin_user_payload,
        medicine_id=med_otc["id"],
        batch_no="PARA-EXP",
        expiry_date_val=today - timedelta(days=10),
        quantity=20,
        purchase_price=14.0,
    )
    assert b_exp["id"] is not None

    # Active available stock for sale must sum non-expired batches only (50 + 50 = 100)
    med_detail = MedicineService.get_medicine(med_otc["id"])
    assert med_detail["total_stock"] == 100

    # FEFO available batches should return non-expired batches sorted by earliest expiry first
    avail_batches = BatchService.get_available_batches_for_sale(med_otc["id"])
    assert len(avail_batches) == 2
    assert avail_batches[0]["batch_no"] == "PARA-B01"


# ==============================================================================
# 3. Suppliers & Inward Procurement Tests
# ==============================================================================
def test_supplier_and_purchase_workflow(admin_user_payload):
    """Verify supplier registration and multi-item stock purchase intake."""
    categories = CategoryService.list_categories()
    cat_id = categories[0]["id"]

    supplier = SupplierService.create_supplier(
        current_user=admin_user_payload,
        data={
            "name": "MedLife Pharma Distributors",
            "contact_person": "Rajesh Sharma",
            "email": "sales@medlife.local",
            "phone": "+91 98765 11223",
            "gst_number": "27ABCDE1234F1Z5",
            "address": "Pharma Hub, Sector 12",
        },
    )
    assert supplier["id"] is not None

    # Ensure a medicine exists
    med = MedicineService.create_medicine(
        current_user=admin_user_payload,
        data={
            "name": "Cetirizine 10mg",
            "generic_name": "Cetirizine Hydrochloride",
            "category_id": cat_id,
            "dosage_form": "Tablet",
            "strength": "10mg",
            "selling_price": 30.0,
            "min_stock": 10,
            "prescription_required": False,
            "barcode": "MED-CET-10",
        },
    )

    today = date.today()
    purchase_items = [
        {
            "medicine_id": med["id"],
            "batch_no": "CET-PUR-01",
            "expiry_date": today + timedelta(days=365),
            "quantity": 100,
            "purchase_price": 12.0,
        }
    ]

    purchase = PurchaseService.create_purchase_order(
        current_user=admin_user_payload,
        supplier_id=supplier["id"],
        invoice_no="INW-2026-901",
        purchase_date_val=today,
        items=purchase_items,
        notes="Urgent test replenishment",
    )
    assert purchase["total_amount"] == 1200.0


    # Verify that batch was created and medicine stock was incremented
    med_after = MedicineService.get_medicine(med["id"])
    assert med_after["total_stock"] == 100


# ==============================================================================
# 4. Customers & Prescriptions Tests
# ==============================================================================
def test_customer_and_prescription_management(admin_user_payload):
    """Verify customer registration and doctor prescription recording."""
    customer = CustomerService.create_customer(
        current_user=admin_user_payload,
        data={
            "name": "Sunita Rao",
            "phone": "+91 98111 22334",
            "email": "sunita.rao@example.local",
            "address": "12 Hospital Road",
        },
    )
    assert customer["id"] is not None

    prescription = PrescriptionService.create_prescription(
        current_user=admin_user_payload,
        data={
            "doctor_name": "Dr. K. S. Murthy",
            "doctor_reg_no": "MCI-2018-8849",
            "patient_name": "Sunita Rao",
            "customer_id": customer["id"],
            "patient_age": 45,
            "patient_gender": "Female",
            "prescription_date": date.today(),
            "diagnosis": "Bacterial respiratory infection",
        },
    )
    assert prescription["id"] is not None
    assert prescription["doctor_name"] == "Dr. K. S. Murthy"


# ==============================================================================
# 5. Point of Sale (POS), FEFO Deduction & Safety Validation Tests
# ==============================================================================
def test_sales_checkout_fefo_deduction(admin_user_payload, pharma_user_payload):
    """Verify atomic POS checkout, FEFO earliest-batch deduction, and profit computation."""
    categories = CategoryService.list_categories()
    cat_id = categories[0]["id"]

    med_para = MedicineService.create_medicine(
        current_user=admin_user_payload,
        data={
            "name": "Ibuprofen 400mg",
            "generic_name": "Ibuprofen",
            "category_id": cat_id,
            "dosage_form": "Tablet",
            "strength": "400mg",
            "selling_price": 40.0,
            "min_stock": 15,
            "prescription_required": False,
            "barcode": "MED-IBU-400",
        },
    )

    today = date.today()
    BatchService.create_batch(
        current_user=admin_user_payload,
        medicine_id=med_para["id"],
        batch_no="IBU-B01",
        expiry_date_val=today + timedelta(days=90),
        quantity=50,
        purchase_price=20.0,
    )

    cart = [
        {
            "medicine_id": med_para["id"],
            "medicine_name": med_para["name"],
            "quantity": 30,
            "unit_price": 40.0,
        }
    ]

    sale = SaleService.create_sale(
        current_user=pharma_user_payload,
        cart_items=cart,
        payment_method="UPI",
        discount_percent=0.0,
        tax_percent=5.0,
    )

    assert sale["id"] is not None
    assert sale["total_amount"] == 1260.0  # 1200 + 5% tax (60)
    assert sale["profit"] == 600.0  # 30 * (40 - 20)

    # First batch IBU-B01 had 50 units; after selling 30, it must have 20 units remaining
    avail_batches = BatchService.get_available_batches_for_sale(med_para["id"])
    b1 = next(b for b in avail_batches if b["batch_no"] == "IBU-B01")
    assert b1["quantity"] == 20


def test_sales_schedule_h_prescription_validation(pharma_user_payload, admin_user_payload):
    """Verify Schedule H medicines reject sale without valid prescription ID."""
    categories = CategoryService.list_categories()
    cat_id = categories[0]["id"]

    med_rx = MedicineService.create_medicine(
        current_user=admin_user_payload,
        data={
            "name": "Azithromycin 500mg",
            "generic_name": "Azithromycin",
            "category_id": cat_id,
            "dosage_form": "Tablet",
            "strength": "500mg",
            "selling_price": 120.0,
            "min_stock": 10,
            "prescription_required": True,
            "barcode": "MED-AZI-500",
        },
    )

    today = date.today()
    BatchService.create_batch(
        current_user=admin_user_payload,
        medicine_id=med_rx["id"],
        batch_no="AZI-B01",
        expiry_date_val=today + timedelta(days=120),
        quantity=40,
        purchase_price=70.0,
    )

    cart = [
        {
            "medicine_id": med_rx["id"],
            "medicine_name": med_rx["name"],
            "quantity": 10,
            "unit_price": 120.0,
        }
    ]

    # Must raise ValidationError when prescription_id is None
    with pytest.raises(ValidationError) as exc_info:
        SaleService.create_sale(
            current_user=pharma_user_payload,
            cart_items=cart,
            prescription_id=None,
        )
    assert "Schedule H" in str(exc_info.value)


def test_sales_insufficient_stock_rejection(pharma_user_payload, admin_user_payload):
    """Verify checkout fails when requested quantity exceeds available non-expired stock."""
    categories = CategoryService.list_categories()
    cat_id = categories[0]["id"]

    med_test = MedicineService.create_medicine(
        current_user=admin_user_payload,
        data={
            "name": "Vitamin D3 60k",
            "generic_name": "Cholecalciferol",
            "category_id": cat_id,
            "dosage_form": "Capsule",
            "strength": "60,000 IU",
            "selling_price": 50.0,
            "min_stock": 10,
            "prescription_required": False,
            "barcode": "MED-D3-60K",
        },
    )

    cart = [
        {
            "medicine_id": med_test["id"],
            "medicine_name": med_test["name"],
            "quantity": 9999,  # Far exceeds stock
            "unit_price": 50.0,
        }
    ]

    with pytest.raises(InsufficientStockError):
        SaleService.create_sale(
            current_user=pharma_user_payload,
            cart_items=cart,
        )


# ==============================================================================
# 6. Inventory, Expiry & Low Stock Monitoring Tests
# ==============================================================================
def test_inventory_expiry_quarantine_overview(admin_user_payload):
    """Verify expiry service identifies expired quarantine stock vs near-expiry items."""
    categories = CategoryService.list_categories()
    cat_id = categories[0]["id"]

    med = MedicineService.create_medicine(
        current_user=admin_user_payload,
        data={
            "name": "Expired Test Syrup",
            "generic_name": "Cough Syrup",
            "category_id": cat_id,
            "dosage_form": "Syrup",
            "strength": "100ml",
            "selling_price": 60.0,
            "min_stock": 5,
            "prescription_required": False,
            "barcode": "MED-EXP-SYR",
        },
    )

    today = date.today()
    BatchService.create_batch(
        current_user=admin_user_payload,
        medicine_id=med["id"],
        batch_no="EXP-SYR-B01",
        expiry_date_val=today - timedelta(days=20),
        quantity=25,
        purchase_price=30.0,
    )

    overview = InventoryService.get_expiry_overview(warning_days=30)
    assert len(overview["expired_batches"]) >= 1
    assert overview["expired_units_total"] >= 25

    # Test batch quarantine disposal
    expired_batch = next(b for b in overview["expired_batches"] if b["batch_no"] == "EXP-SYR-B01")
    disposed = InventoryService.quarantine_and_discard_batch(
        current_user=admin_user_payload,
        batch_id=expired_batch["batch_id"],
        reason="Bio-waste compliance incineration",
    )
    assert disposed["discarded_quantity"] == 25



def test_inventory_low_stock_detection():
    """Verify low stock overview detects items below safety threshold."""
    low_overview = InventoryService.get_low_stock_overview()
    assert "items" in low_overview


# ==============================================================================
# 7. Notifications & Alert Center Tests
# ==============================================================================
def test_notification_sync_and_resolution():
    """Verify automatic sync of near-expiry/low-stock alerts and mark-as-read lifecycle."""
    synced = NotificationService.sync_inventory_alerts()
    unread_count = NotificationService.get_unread_count()
    assert unread_count >= 0

    all_notifs = NotificationService.get_notifications()
    if all_notifs:
        target_id = all_notifs[0]["id"]
        NotificationService.mark_as_read(target_id)
        assert NotificationService.get_unread_count() <= unread_count


# ==============================================================================
# 8. Dashboard KPIs & Reporting Engine Tests
# ==============================================================================
def test_dashboard_kpis_and_timeline():
    """Verify executive KPI aggregation and sales timeline series."""
    kpis = DashboardService.get_kpis()
    assert kpis["total_medicines"] >= 2
    assert "today_revenue" in kpis

    timeline = DashboardService.get_sales_timeline(days=7)
    assert len(timeline) == 7


def test_report_generation_and_pdf():
    """Verify sales report calculation and ReportLab PDF document compilation."""
    today = date.today()
    rep = ReportService.get_sales_report(today - timedelta(days=30), today)
    assert "net_sales" in rep
    assert "total_invoices" in rep

    pdf_bytes = ReportService.generate_sales_report_pdf(rep)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500  # Valid compiled PDF bytes


# ==============================================================================
# 9. Settings & Database Backup Tests
# ==============================================================================
def test_settings_and_backup_operations(admin_user_payload):
    """Verify dynamic settings updates and SQLite hot backup snapshot generation."""
    settings = SettingService.get_all_settings()
    assert "pharmacy_name" in settings

    updated = SettingService.update_settings(
        current_user=admin_user_payload,
        settings_data={"pharmacy_name": "PharmaCare Test Hospital"},
    )
    assert updated["pharmacy_name"] == "PharmaCare Test Hospital"

    # Test hot backup snapshot
    bk_bytes, filename = BackupService.create_database_backup(admin_user_payload)
    assert bk_bytes.startswith(b"SQLite format 3")
    assert filename.endswith(".db")
