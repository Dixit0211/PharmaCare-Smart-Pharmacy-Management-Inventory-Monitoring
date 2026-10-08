# PharmaCare – Academic Project Report & Viva Reference Guide

**Project Title:** PharmaCare – Smart Pharmacy Management & Inventory Monitoring System  
**Architecture:** 3-Tier Enterprise Architecture (UI $\rightarrow$ Domain Services $\rightarrow$ Data Models)  
**Technology Stack:** Python 3.11/3.14, Streamlit, SQLAlchemy 2.x, SQLite, ReportLab, Plotly, bcrypt  

---

## 1. Executive Summary & Problem Statement

Retail and hospital pharmacies operate in a highly regulated domain where medication errors, stock expiration, and prescription non-compliance carry severe legal and health consequences. Traditional pharmacy workflows suffer from four major challenges:
1. **Financial Waste from Expired Stock:** Medicines expire unnoticed on shelves because stock is dispensed randomly rather than prioritized by expiration date.
2. **Regulatory Non-Compliance (Schedule H Violations):** Antibiotics and controlled narcotics are dispensed without recording mandatory doctor prescription details.
3. **Stock-Outs of Critical Life-Saving Drugs:** Inventory is only counted periodically, leading to emergency shortages of essential medications.
4. **Lack of Transparent Auditability:** Paper records or legacy desktop systems allow untracked modifications and lack immutable audit logs.

**PharmaCare** was engineered to solve these challenges through:
- **First-Expiry-First-Out (FEFO) Engine:** Automatically allocates physical batches with the earliest expiry date first during counter dispensing.
- **Statutory Expiry Quarantine:** Prevents expired batches from ever being added to a sales cart, calculating financial loss and requiring auditable disposal.
- **Schedule H Compliance Enforcement:** Programmatically blocks checkout for prescription-required drugs unless linked to an active prescription record.
- **Immutable Compliance Trail:** Logs all authentication attempts, stock adjustments, sales transactions, and database operations.

---

## 2. System Architecture

```
+-----------------------------------------------------------------------+
|                       PRESENTATION LAYER (Streamlit)                  |
|   app/pages/ (Dashboard, POS Billing, Inventory, Expiry, Reports)     |
|   app/components/ (Styles, Metric Cards, Status Badges, Data Tables)  |
+-----------------------------------------------------------------------+
                                  │
                                  │ Calls typed domain methods
                                  ▼
+-----------------------------------------------------------------------+
|                        DOMAIN SERVICE LAYER                           |
|   app/services/ (Auth, Medicine, Batch, Inventory, Sale, Report, etc) |
|   * Business Rules  * RBAC Decorators  * Transactions  * Exceptions   |
+-----------------------------------------------------------------------+
                                  │
                                  │ SQLAlchemy 2.0 ORM sessions
                                  ▼
+-----------------------------------------------------------------------+
|                         DATA ACCESS LAYER                             |
|   app/models/ (User, Medicine, Batch, Purchase, Sale, Prescription)   |
|   app/core/database.py (SQLite PRAGMA foreign_keys = ON)              |
+-----------------------------------------------------------------------+
```

---

## 3. Key Technical Highlights for Viva

### 3.1 First-Expiry-First-Out (FEFO) Stock Allocation
When a customer requests $N$ units of a medicine:
1. `SaleService` queries `MedicineBatch` filtered by `medicine_id == id`, `expiry_date >= today`, and `quantity > 0`, sorted by `expiry_date.asc()`.
2. The algorithm iterates through available batches, allocating units from the earliest expiring batch first.
3. If the batch does not satisfy $N$, it exhausts that batch (`qty = 0`) and continues to the next earliest batch until $N$ is fulfilled.
4. Each dispensed batch slice is saved as an individual `SaleItem` referencing its exact `batch_id` and recording historical `purchase_price` to accurately compute profit.

### 3.2 Direct bcrypt Cryptographic Hashing
To prevent compatibility bugs with legacy wrappers, passwords are authenticated and hashed using direct `bcrypt.hashpw` and `bcrypt.checkpw` on UTF-8 encoded bytes with automatic truncation to 72 bytes.

### 3.3 Dynamic SQLite PRAGMA Foreign Keys
SQLite disables foreign key constraint enforcement by default. PharmaCare registers a SQLAlchemy event listener `connect` that automatically executes `PRAGMA foreign_keys=ON` on every raw database connection, preventing orphaned records.

---

## 4. Top 10 Viva Questions & Model Answers

**Q1: What is the difference between FIFO and FEFO in pharmacy management?**  
*Answer:* FIFO (First-In-First-Out) dispenses stock based on the date it was received in the warehouse. FEFO (First-Expiry-First-Out) dispenses stock based on the product's actual expiration date, regardless of when it was received. In pharmaceuticals, FEFO is mandatory because a newer shipment might have a shorter shelf-life than an older batch.

**Q2: How does PharmaCare prevent dispensing expired medications?**  
*Answer:* When querying available batches for sale, `SaleService` enforces a strict SQL filter `expiry_date >= today`. If a pharmacist attempts to manually select an expired batch, `SaleService` rejects the operation with a typed `ExpiredBatchError`. Expired batches are routed to the *Expiry Quarantine Monitor* for audited disposal.

**Q3: Why did you choose a 3-Layer Architecture over writing database code directly in Streamlit pages?**  
*Answer:* Writing database queries directly in UI scripts violates Separation of Concerns and leads to code duplication, transaction leaks, and untestable logic. With 3-Layer Architecture, UI pages only handle presentation, while all business rules and database transactions live in reusable domain services that can be independently unit-tested with `pytest`.

**Q4: How does PharmaCare enforce Role-Based Access Control (RBAC)?**  
*Answer:* We implemented a custom Python decorator `@require_role("admin")` in domain services. When an unauthorized user attempts an administrative operation (e.g. creating users, modifying settings, or deleting records), the decorator intercepts the call and raises `PermissionDeniedException`, which the UI catches and displays as an error.

**Q5: How is profit calculated accurately when drug procurement costs fluctuate over time?**  
*Answer:* When a sale occurs, each `SaleItem` records the exact `purchase_price` from the specific `MedicineBatch` that was dispensed. Profit is computed as `subtotal - (quantity * purchase_price)` for each line item. This guarantees historical financial accuracy even if procurement costs rise in subsequent shipments.

**Q6: What happens if a pharmacist tries to bill a Schedule H drug without a prescription?**  
*Answer:* `Medicine` has a boolean flag `prescription_required`. During checkout, `SaleService` inspects every cart item. If any item has `prescription_required == True` and `prescription_id` is null, the transaction is rejected with a `ValidationError`.

**Q7: How are system alerts synchronized without slowing down the user experience?**  
*Answer:* `NotificationService.sync_inventory_alerts()` performs a targeted single-pass SQL scan comparing `expiry_date` and `min_stock` thresholds. It uses duplicate suppression to ensure that if an unread alert already exists for a batch or medicine, redundant duplicate alerts are not generated.

**Q8: How does database backup work in SQLite without stopping live counters?**  
*Answer:* `BackupService` utilizes SQLite's native Online Backup API (`sqlite3.Connection.backup()`), which performs a hot-copy of the database pages while allowing concurrent read transactions without database file locking.

**Q9: How are PDF invoices and sales reports generated?**  
*Answer:* We utilize **ReportLab** to programmatically build vector PDF documents in memory (`io.BytesIO`). The document uses custom `TableStyle`, `ParagraphStyle`, and `SimpleDocTemplate` to render official GST compliant invoices with pharmacy licensing details, line-item breakdowns, and statutory disclaimers.

**Q10: How do you ensure database integrity during unexpected system crashes?**  
*Answer:* All multi-step mutations (such as sales billing which modifies batches, creates invoices, and adds sale items) are wrapped inside Python context-managed SQLAlchemy sessions (`with get_db() as session:`). If any step fails, the entire transaction is automatically rolled back, preserving atomic database consistency.
