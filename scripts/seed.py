"""Seed script to populate PharmaCare with realistic demo data for college viva and demonstration."""

import sys
import random
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.database import Base, engine, SessionLocal, init_db
from app.core.security import hash_password
from app.models import (
    User,
    Category,
    Supplier,
    Customer,
    Medicine,
    MedicineBatch,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    Prescription,
    Notification,
    AuditLog,
    AppSetting,
)


def seed_database() -> None:
    """Populate database with clean, comprehensive demo data."""
    print("🚀 Initializing database schema...")
    init_db()

    session = SessionLocal()
    try:
        # Check if already seeded
        existing_users = session.query(User).count()
        if existing_users > 0:
            print("⚠️  Database already contains records. Resetting tables for a clean seed...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)

        today = date.today()
        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. System Settings
        # -------------------------------------------------------------
        print("⚙️  Seeding system settings...")
        settings_data = [
            ("pharmacy_name", "PharmaCare Central Pharmacy", "Official registered pharmacy name"),
            ("pharmacy_address", "104 Healthcare Boulevard, Medical District, City - 400001", "Physical store address"),
            ("pharmacy_phone", "+91 98765 43210", "Store contact phone number"),
            ("pharmacy_email", "contact@pharmacare.local", "Store official email address"),
            ("pharmacy_gst", "27ABCDE1234F1Z5", "GST / Tax Identification Number"),
            ("pharmacy_license", "DL-2024-MH-99482 / 21B", "Drug dispensing license number"),
            ("expiry_warning_days", "30", "Days before expiry to trigger warning alert"),
            ("default_min_stock", "15", "Default minimum stock threshold for reordering"),
            ("tax_percentage", "5.0", "Default applicable GST / Tax rate in percent"),
            ("invoice_prefix", "INV-PHARMA", "Prefix used for customer sales invoices"),
            ("session_timeout_minutes", "480", "Inactivity timeout in minutes for user sessions"),
        ]
        for key, val, desc in settings_data:
            session.add(AppSetting(key=key, value=val, description=desc))

        # -------------------------------------------------------------
        # 2. Users (Admin and Pharmacist)
        # -------------------------------------------------------------
        print("👤 Seeding system users (Admin & Pharmacist)...")
        admin_user = User(
            username="admin",
            email="admin@pharmacare.local",
            password_hash=hash_password("Admin@123"),
            full_name="Dr. Alok Verma (Admin)",
            role="admin",
            phone="+91 98111 22233",
            is_active=True,
        )
        pharmacist_user = User(
            username="pharmacist",
            email="pharmacist@pharmacare.local",
            password_hash=hash_password("Pharma@123"),
            full_name="Neha Deshmukh (Pharmacist)",
            role="pharmacist",
            phone="+91 98222 33344",
            is_active=True,
        )
        session.add_all([admin_user, pharmacist_user])
        session.flush()

        # -------------------------------------------------------------
        # 3. Categories
        # -------------------------------------------------------------
        print("🏷️  Seeding pharmaceutical categories...")
        categories_map = {
            "Analgesics & Antipyretics": "Pain relief and fever reducing medications",
            "Antibiotics": "Antimicrobial agents for bacterial infections",
            "Antihistamines": "Allergy relief and anti-inflammatory compounds",
            "Gastrointestinal": "Antacids, proton pump inhibitors and digestive aids",
            "Antidiabetic": "Blood sugar regulation and diabetes management",
            "Vitamins & Supplements": "Nutritional dietary supplements and immunity boosters",
            "Cardiovascular": "Blood pressure and heart health medications",
        }
        category_objs = {}
        for cat_name, desc in categories_map.items():
            cat = Category(name=cat_name, description=desc)
            session.add(cat)
            category_objs[cat_name] = cat
        session.flush()

        # -------------------------------------------------------------
        # 4. Suppliers
        # -------------------------------------------------------------
        print("🏢 Seeding wholesale distributors & suppliers...")
        suppliers_data = [
            (
                "Apollo MedSupply Distributors",
                "Ramesh Gupta",
                "+91 98333 44455",
                "orders@apollomedsupply.com",
                "Unit 12, Industrial Pharma Park, Sector 4",
                "27AAACA1234A1Z1",
            ),
            (
                "Cipla Healthcare Wholesale",
                "Sanjay Mehta",
                "+91 98444 55566",
                "distribution@cipladirect.com",
                "Cipla Commercial Complex, Andheri East",
                "27AAACC5678B1Z2",
            ),
            (
                "Sun Pharma Direct Logistics",
                "Anil Kulkarni",
                "+91 98555 66677",
                "support@sunpharmalogistics.com",
                "Plot 88, MIDC Central Road, Pune",
                "27AAACS9012C1Z3",
            ),
            (
                "Mankind Lifecare Supply",
                "Vikram Shinde",
                "+91 98666 77788",
                "sales@mankindlifecare.com",
                "Warehouse 4B, Bhiwandi Logistics Hub",
                "27AAACM3456D1Z4",
            ),
        ]
        supplier_objs = []
        for name, cp, phone, email, addr, gst in suppliers_data:
            sup = Supplier(
                name=name,
                contact_person=cp,
                phone=phone,
                email=email,
                address=addr,
                gst_number=gst,
            )
            session.add(sup)
            supplier_objs.append(sup)
        session.flush()

        # -------------------------------------------------------------
        # 5. Customers
        # -------------------------------------------------------------
        print("👥 Seeding patient and customer profiles...")
        customers_data = [
            ("Rajesh Sharma", "+91 98700 11223", "rajesh.sharma@example.com", "Flat 402, Sunshine Apts, MG Road"),
            ("Priya Patel", "+91 98700 22334", "priya.patel@example.com", "B-12, Greenview Enclave, Station Road"),
            ("Amit Verma", "+91 98700 33445", "amit.verma@example.com", "15/A Gokul Society, Subhash Chowk"),
            ("Sunita Rao", "+91 98700 44556", "sunita.rao@example.com", "C-301, Lake Palace, Palm Beach Road"),
            ("Vikram Malhotra", "+91 98700 55667", "vikram.m@example.com", "House 88, Model Town Extension"),
        ]
        customer_objs = []
        for name, phone, email, addr in customers_data:
            cust = Customer(name=name, phone=phone, email=email, address=addr)
            session.add(cust)
            customer_objs.append(cust)
        session.flush()

        # -------------------------------------------------------------
        # 6. Prescriptions
        # -------------------------------------------------------------
        print("📝 Seeding valid medical prescriptions...")
        rx1 = Prescription(
            customer_id=customer_objs[0].id,
            doctor_name="Dr. Sneha Roy, MD",
            doctor_reg_no="MCI-88492-A",
            patient_name="Rajesh Sharma",
            patient_age=48,
            patient_gender="Male",
            prescription_date=today - timedelta(days=10),
            diagnosis="Type 2 Diabetes Mellitus & Acute Bronchitis",
            notes="Take Amoxicillin 500mg after food twice daily. Metformin with dinner.",
        )
        rx2 = Prescription(
            customer_id=customer_objs[1].id,
            doctor_name="Dr. K. V. Joshi, MBBS",
            doctor_reg_no="MCI-44102-B",
            patient_name="Priya Patel",
            patient_age=32,
            patient_gender="Female",
            prescription_date=today - timedelta(days=5),
            diagnosis="Upper Respiratory Tract Infection",
            notes="Azithromycin 500mg once daily for 5 days.",
        )
        rx3 = Prescription(
            customer_id=customer_objs[2].id,
            doctor_name="Dr. Sneha Roy, MD",
            doctor_reg_no="MCI-88492-A",
            patient_name="Amit Verma",
            patient_age=55,
            patient_gender="Male",
            prescription_date=today - timedelta(days=2),
            diagnosis="Glycemic Control maintenance",
            notes="Metformin 500mg regular maintenance dose.",
        )
        session.add_all([rx1, rx2, rx3])
        session.flush()

        # -------------------------------------------------------------
        # 7. Medicines & Batches (Safe, Near-Expiry, Expired, Low Stock)
        # -------------------------------------------------------------
        print("💊 Seeding master medicines catalog & batch inventory...")

        # Medicine definitions:
        # (name, generic, brand, cat_key, mfr, barcode, form, strength, selling_price, min_stock, rx_req)
        meds_info = [
            (
                "Paracetamol 500mg",
                "Paracetamol / Acetaminophen",
                "Crocin / Calpol",
                "Analgesics & Antipyretics",
                "GSK Healthcare",
                "890103000101",
                "Tablet",
                "500mg",
                25.00,
                20,
                False,
            ),
            (
                "Amoxicillin 500mg",
                "Amoxicillin Trihydrate",
                "Mox 500",
                "Antibiotics",
                "Ranbaxy Laboratories",
                "890103000102",
                "Capsule",
                "500mg",
                95.00,
                15,
                True,
            ),
            (
                "Cetirizine 10mg",
                "Cetirizine Hydrochloride",
                "Cetzine / Alerid",
                "Antihistamines",
                "Dr. Reddy's Labs",
                "890103000103",
                "Tablet",
                "10mg",
                38.50,
                15,
                False,
            ),
            (
                "Azithromycin 500mg",
                "Azithromycin",
                "Azithral 500",
                "Antibiotics",
                "Alembic Pharma",
                "890103000104",
                "Tablet",
                "500mg",
                125.00,
                25,  # We will set stock to 6 to trigger LOW STOCK
                True,
            ),
            (
                "Vitamin C 500mg",
                "Ascorbic Acid",
                "Limcee / Celin",
                "Vitamins & Supplements",
                "Abbott Healthcare",
                "890103000105",
                "Chewable Tablet",
                "500mg",
                30.00,
                20,
                False,
            ),
            (
                "Omeprazole 20mg",
                "Omeprazole",
                "Omez 20",
                "Gastrointestinal",
                "Dr. Reddy's Labs",
                "890103000106",
                "Capsule",
                "20mg",
                55.00,
                15,
                False,
            ),
            (
                "Metformin 500mg",
                "Metformin Hydrochloride",
                "Glycomet 500",
                "Antidiabetic",
                "USV Private Ltd",
                "890103000107",
                "Tablet",
                "500mg",
                42.00,
                30,
                True,
            ),
            (
                "Ibuprofen 400mg",
                "Ibuprofen",
                "Brufen 400",
                "Analgesics & Antipyretics",
                "Abbott Healthcare",
                "890103000108",
                "Tablet",
                "400mg",
                32.00,
                15,
                False,
            ),
        ]

        medicine_objs = []
        for (
            name,
            gen,
            brand,
            cat_key,
            mfr,
            barcode,
            form,
            strength,
            price,
            min_stk,
            rx_req,
        ) in meds_info:
            med = Medicine(
                name=name,
                generic_name=gen,
                brand=brand,
                category_id=category_objs[cat_key].id,
                manufacturer=mfr,
                barcode=barcode,
                dosage_form=form,
                strength=strength,
                selling_price=price,
                min_stock=min_stk,
                prescription_required=rx_req,
                status="active",
            )
            session.add(med)
            medicine_objs.append(med)
        session.flush()

        # Batch definitions ensuring all states: Safe, Expiring Soon, Expired, Low Stock
        # (med_idx, batch_no, expiry_offset_days, qty, purchase_price)
        batches_plan = [
            # 0: Paracetamol (Safe batches + 1 Expired historical batch)
            (0, "PARA-2024-B1", 360, 120, 15.00),  # Safe
            (0, "PARA-2024-B2", 540, 80, 15.50),   # Safe
            (0, "PARA-2023-OLD", -45, 12, 14.00),  # Expired (45 days ago)

            # 1: Amoxicillin (Safe batch)
            (1, "AMOX-2024-A1", 400, 60, 65.00),   # Safe
            (1, "AMOX-2024-A2", 200, 40, 67.00),   # Safe

            # 2: Cetirizine (Safe + 1 Expiring Soon batch)
            (2, "CET-2024-C1", 420, 90, 22.00),    # Safe
            (2, "CET-2024-NEAR", 18, 25, 20.00),   # Expiring soon (18 days left)

            # 3: Azithromycin (LOW STOCK: only 6 total units vs min_stock=25)
            (3, "AZI-2024-Z1", 300, 6, 85.00),     # Safe expiry, but Low Stock (6 units)

            # 4: Vitamin C (Safe + 1 Expiring Soon batch)
            (4, "VITC-2024-V1", 500, 150, 18.00),  # Safe
            (4, "VITC-2024-NEAR", 12, 35, 17.50),  # Expiring soon (12 days left)

            # 5: Omeprazole (Safe batches)
            (5, "OMZ-2024-O1", 380, 75, 34.00),    # Safe
            (5, "OMZ-2024-O2", 520, 50, 35.00),    # Safe

            # 6: Metformin (Safe batches)
            (6, "MET-2024-M1", 450, 140, 26.00),   # Safe
            (6, "MET-2024-M2", 600, 100, 27.00),   # Safe

            # 7: Ibuprofen (Safe + 1 Expired batch)
            (7, "IBU-2024-I1", 320, 70, 19.00),    # Safe
            (7, "IBU-2023-EXP", -20, 18, 18.00),   # Expired (20 days ago)
        ]

        batch_objs = []
        for med_idx, b_no, exp_offset, qty, p_price in batches_plan:
            b_exp = today + timedelta(days=exp_offset)
            batch = MedicineBatch(
                medicine_id=medicine_objs[med_idx].id,
                batch_no=b_no,
                expiry_date=b_exp,
                quantity=qty,
                purchase_price=p_price,
            )
            session.add(batch)
            batch_objs.append(batch)
        session.flush()

        # -------------------------------------------------------------
        # 8. Purchases (Inward Invoices)
        # -------------------------------------------------------------
        print("📦 Seeding procurement purchase invoices...")
        p1 = Purchase(
            supplier_id=supplier_objs[0].id,
            invoice_no="PUR-2024-001",
            purchase_date=today - timedelta(days=40),
            total_amount=5450.00,
            status="received",
            notes="Bulk monthly replenishment for Analgesics and Antihistamines",
        )
        p2 = Purchase(
            supplier_id=supplier_objs[1].id,
            invoice_no="PUR-2024-002",
            purchase_date=today - timedelta(days=25),
            total_amount=9200.00,
            status="received",
            notes="Antibiotics and Antidiabetic stock procurement",
        )
        session.add_all([p1, p2])
        session.flush()

        pi1 = PurchaseItem(
            purchase_id=p1.id,
            medicine_id=medicine_objs[0].id,
            batch_no="PARA-2024-B1",
            expiry_date=today + timedelta(days=360),
            quantity=150,
            purchase_price=15.00,
            subtotal=2250.00,
        )
        pi2 = PurchaseItem(
            purchase_id=p1.id,
            medicine_id=medicine_objs[2].id,
            batch_no="CET-2024-C1",
            expiry_date=today + timedelta(days=420),
            quantity=100,
            purchase_price=22.00,
            subtotal=2200.00,
        )
        pi3 = PurchaseItem(
            purchase_id=p2.id,
            medicine_id=medicine_objs[1].id,
            batch_no="AMOX-2024-A1",
            expiry_date=today + timedelta(days=400),
            quantity=80,
            purchase_price=65.00,
            subtotal=5200.00,
        )
        session.add_all([pi1, pi2, pi3])
        session.flush()

        # -------------------------------------------------------------
        # 9. Sales History (~30 days of realistic billing records)
        # -------------------------------------------------------------
        print("🧾 Seeding 30 days of sales history & billing records...")
        payment_methods = ["Cash", "UPI", "Card", "Cash", "UPI"]

        # List of safe saleable batches (index in batch_objs)
        # 0: PARA-B1, 3: AMOX-A1, 5: CET-C1, 7: AZI-Z1, 8: VITC-V1, 10: OMZ-O1, 12: MET-M1, 14: IBU-I1
        saleable_pool = [
            (medicine_objs[0], batch_objs[0], 25.00, 15.00, False),
            (medicine_objs[1], batch_objs[3], 95.00, 65.00, True),
            (medicine_objs[2], batch_objs[5], 38.50, 22.00, False),
            (medicine_objs[4], batch_objs[8], 30.00, 18.00, False),
            (medicine_objs[5], batch_objs[10], 55.00, 34.00, False),
            (medicine_objs[6], batch_objs[12], 42.00, 26.00, True),
            (medicine_objs[7], batch_objs[14], 32.00, 19.00, False),
        ]

        inv_counter = 101
        for day_offset in range(30, -1, -1):
            sale_dt = now - timedelta(days=day_offset, hours=random.randint(1, 10), minutes=random.randint(5, 50))
            num_sales_today = random.randint(1, 3)

            for _ in range(num_sales_today):
                inv_no = f"INV-2024-{inv_counter}"
                inv_counter += 1

                cust = random.choice(customer_objs) if random.random() > 0.3 else None
                pay_method = random.choice(payment_methods)

                # Pick 1-3 distinct medicines for this sale
                selected_meds = random.sample(saleable_pool, k=random.randint(1, 3))
                
                # Check if any requires prescription
                has_rx = any(item[4] for item in selected_meds)
                rx_id = rx1.id if has_rx else None

                subtotal = 0.0
                sale_items_to_add = []

                for med_item, batch_item, s_price, p_price, _ in selected_meds:
                    qty = random.randint(1, 3)
                    line_total = round(qty * s_price, 2)
                    subtotal += line_total
                    sale_items_to_add.append(
                        (med_item.id, batch_item.id, qty, s_price, p_price, line_total)
                    )

                discount = round(subtotal * 0.05, 2) if random.random() > 0.7 else 0.0
                tax = round((subtotal - discount) * 0.05, 2)
                total = round(subtotal - discount + tax, 2)

                sale = Sale(
                    invoice_no=inv_no,
                    customer_id=cust.id if cust else None,
                    prescription_id=rx_id,
                    user_id=pharmacist_user.id,
                    payment_method=pay_method,
                    subtotal=subtotal,
                    discount=discount,
                    tax=tax,
                    total_amount=total,
                    sale_date=sale_dt,
                    notes="Counter billing - routine prescription and OTC dispense",
                )
                session.add(sale)
                session.flush()

                for m_id, b_id, q, u_p, p_p, s_t in sale_items_to_add:
                    si = SaleItem(
                        sale_id=sale.id,
                        medicine_id=m_id,
                        batch_id=b_id,
                        quantity=q,
                        unit_price=u_p,
                        purchase_price=p_p,
                        subtotal=s_t,
                    )
                    session.add(si)

        session.flush()

        # -------------------------------------------------------------
        # 10. Initial Notifications (derived alerts)
        # -------------------------------------------------------------
        print("🔔 Seeding initial system notifications...")
        notifications = [
            Notification(
                type="low_stock",
                severity="critical",
                title="Low Stock Alert: Azithromycin 500mg",
                message="Azithromycin 500mg total stock is 6 units, which is below the minimum threshold of 25 units. Reorder recommended.",
                reference_id=medicine_objs[3].id,
                is_read=False,
            ),
            Notification(
                type="expiry",
                severity="critical",
                title="Expired Batch Detected: Paracetamol 500mg",
                message="Batch PARA-2023-OLD expired on " + str(today - timedelta(days=45)) + ". Please quarantine and discard.",
                reference_id=batch_objs[2].id,
                is_read=False,
            ),
            Notification(
                type="expiry",
                severity="warning",
                title="Near-Expiry Warning: Vitamin C 500mg",
                message="Batch VITC-2024-NEAR is expiring in 12 days (" + str(today + timedelta(days=12)) + "). Prioritize FEFO dispensing.",
                reference_id=batch_objs[9].id,
                is_read=False,
            ),
            Notification(
                type="expiry",
                severity="warning",
                title="Near-Expiry Warning: Cetirizine 10mg",
                message="Batch CET-2024-NEAR is expiring in 18 days (" + str(today + timedelta(days=18)) + ").",
                reference_id=batch_objs[6].id,
                is_read=True,
            ),
            Notification(
                type="system",
                severity="info",
                title="System Initialized",
                message="PharmaCare database schema initialized with standard pharmaceutical catalogs and demo records.",
                reference_id=None,
                is_read=True,
            ),
        ]
        session.add_all(notifications)

        # -------------------------------------------------------------
        # 11. Initial Audit Logs
        # -------------------------------------------------------------
        print("🛡️  Seeding initial compliance audit logs...")
        audit_logs = [
            AuditLog(
                user_id=admin_user.id,
                username="admin",
                action="INITIALIZE",
                module="SYSTEM",
                description="Database schema created and initial configurations set",
                ip_address="127.0.0.1",
            ),
            AuditLog(
                user_id=admin_user.id,
                username="admin",
                action="SEED",
                module="CATALOG",
                description="Master catalog seeded with standard demo medicines, suppliers, and customer profiles",
                ip_address="127.0.0.1",
            ),
            AuditLog(
                user_id=pharmacist_user.id,
                username="pharmacist",
                action="LOGIN",
                module="AUTH",
                description="Pharmacist session login verified",
                ip_address="127.0.0.1",
            ),
        ]
        session.add_all(audit_logs)

        session.commit()
        print("\n✅ Seed process completed successfully!")
        print("--------------------------------------------------")
        print("Default Accounts:")
        print("  🔑 Admin:      admin@pharmacare.local      / Admin@123")
        print("  🔑 Pharmacist: pharmacist@pharmacare.local / Pharma@123")
        print("--------------------------------------------------")

    except Exception as e:
        session.rollback()
        print(f"❌ Error during seed process: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
