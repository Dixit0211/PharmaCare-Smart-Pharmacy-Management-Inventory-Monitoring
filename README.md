# 💊 PharmaCare – Smart Pharmacy Management & Inventory Monitoring System

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-0D9488.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.37%2B-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-16%20Passed%20(100%25)-success.svg?logo=pytest&logoColor=white)](https://pytest.org/)
[![Architecture](https://img.shields.io/badge/Architecture-3--Layer%20Domain-0F172A.svg)]()

> **PharmaCare** is an enterprise-grade academic pharmacy management and inventory monitoring system built entirely in Python. It simulates real-world clinical hospital dispensary operations with statutory **First-Expiry-First-Out (FEFO)** batch allocation, **Schedule H prescription validation**, **automatic expiry quarantine**, **live inventory valuation**, **ReportLab PDF invoicing**, and **immutable audit logging**.

---

## 🌟 Key System Capabilities

- **🛒 Point of Sale (POS) Counter Billing:** Multi-item cart builder, customer profile lookup, instant FEFO earliest-batch allocation, GST tax computation, and instant downloadable **ReportLab PDF Invoices**.
- **⏳ Smart Expiry & Quarantine Monitor:** Real-time categorization into *Expired (Quarantined)*, *Expiring Soon (≤30 Days)*, and *Safe*. Includes financial loss calculation and bio-waste compliance disposal workflows.
- **⚠️ Low-Stock Replenishment Queue:** Tracks available stock against safety thresholds (`min_stock`) and computes suggested purchase reorder quantities.
- **🩺 Schedule H / Rx Prescription Validation:** Restricts dispensing of controlled drugs and antibiotics unless linked to an authorized doctor prescription.
- **📥 Inward Stock Procurement:** Multi-item purchase intake that automatically registers or increments physical batch lots and updates purchase cost records.
- **📊 Interactive Executive Dashboard:** Plotly dual-axis revenue timelines (7/14/30 days), category distribution doughnut charts, top-selling medications, and live alert banners.
- **📑 Comprehensive Financial Reports:** Date-range filtered sales statements, itemized profit margin analytics, live inventory valuation (Cost vs Retail MRP), and PDF summary reports.
- **👥 Role-Based Access Control (RBAC):** Multi-tier permissions (`Admin` vs `Pharmacist`) protecting administrative settings, user management, and audit logs.
- **💾 Database Hot Backup & Restore:** One-click SQLite binary snapshot download and schema-verified file restoration.

---

## 🏗️ 3-Layer Architecture Overview

```
PharmaCare System Architecture
├── Presentation Layer (Streamlit Pages in app/pages/)
│   └── Never touches database sessions; catches typed exceptions & shows clean toasts.
├── Domain Business Services (app/services/)
│   └── All transactions, business rules, FEFO allocation, RBAC guards, and audit logging.
└── Data Access & Models (app/models/ & app/core/database.py)
    └── 14 Declarative SQLAlchemy 2.x models with SQLite foreign key PRAGMA enforcement.
```

---

## 🚀 Quick Start & Installation

### 1. Clone & Setup Environment
```powershell
# Navigate to project directory
cd PharmaCare-Smart-Pharmacy-Management-Inventory-Monitoring

# Create virtual environment (optional)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Database & Seed Demo Data
```powershell
# Run the database seeder (populates users, categories, medicines, batches, customers, and sales)
py scripts/seed.py
```

### 3. Launch the Application
```powershell
py -m streamlit run app/main.py
```

---

## 🧪 Demo Viva Credentials

| Role | Username / Email | Password | Pre-configured Privileges |
|---|---|---|---|
| **👑 Administrator** | `admin@pharmacare.local` | `Admin@123` | Full access to settings, user management, audit logs, backup/restore, and reports. |
| **💊 Staff Pharmacist** | `pharmacist@pharmacare.local` | `Pharma@123` | Counter POS billing, stock inquiry, prescription recording, and customer management. |

> *Quick-login demo buttons are available on the login portal for fast viva demonstration.*

---

## 🧪 Automated Test Suite

Run the full automated `pytest` test suite:
```powershell
py -m pytest tests/test_services.py -v
```

All 16 unit tests test authentication, FEFO deduction, Schedule H prescription enforcement, expired batch rejection, low stock detection, PDF invoice rendering, and backup snapshot creation.

---

## 📂 Project Structure

```
PharmaCare/
├── app/
│   ├── components/       # Custom hospital CSS, metric cards, sidebar, status badges
│   ├── core/             # Configuration, SQLite database engine, security (bcrypt), exceptions
│   ├── models/           # 14 SQLAlchemy 2.x declarative entity models
│   ├── pages/            # 14 Streamlit multipage views (Dashboard, Billing, Inventory, Admin)
│   ├── services/         # 13 Domain business services (Pure Python business logic)
│   ├── utils/            # ReportLab PDF invoice generator, validators, formatters, session
│   └── main.py           # Application entrypoint and st.navigation routing
├── data/                 # SQLite database storage (pharmacare.db)
├── docs/                 # Complete documentation
│   ├── database-schema.md   # Entity-Relationship diagram & data dictionary
│   ├── services-reference.md# Domain services API & exception reference
│   └── project-report.md    # Academic college viva project report & Q&A guide
├── scripts/              # Database seed script (scripts/seed.py)
├── tests/                # Pytest test suite (tests/test_services.py)
├── .streamlit/           # Streamlit clinical teal & slate theme configuration
└── README.md             # Project documentation
```

---

## 📜 License & Viva Information
Designed and developed for academic demonstrations and college viva evaluations. Pure Python implementation without JavaScript or external paid services.