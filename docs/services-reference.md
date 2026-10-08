# PharmaCare Domain Services & Business Logic Reference

This document provides a comprehensive developer reference for all 13 domain business services in the **PharmaCare** architecture.

---

## 1. Architectural Rules & Error Handling

PharmaCare follows a strict **3-Layer Architecture**:
1. **Presentation Layer (`app/pages/`)**: Renders Streamlit UI components, captures user inputs, and presents notifications/toasts. *Pages never touch the SQLAlchemy database session directly or embed business logic.*
2. **Domain Service Layer (`app/services/`)**: Contains all transactions, business rules, FEFO sorting, statutory checks, RBAC decorators, and immutable audit logging. Services raise custom typed exceptions on errors.
3. **Data Access Layer (`app/models/` & `app/core/database.py`)**: Defines SQLAlchemy 2.x declarative models, table relationships, foreign key constraints, and connection pooling.

### Custom Typed Exceptions (`app/core/exceptions.py`)

| Exception | Purpose | HTTP/Viva Analogy |
|---|---|---|
| `AuthenticationError` | Raised on invalid username/password or deactivated accounts | 401 Unauthorized |
| `PermissionDeniedException`| Raised when user role violates `@require_role` restrictions | 403 Forbidden |
| `ValidationError` | Raised on missing required fields, invalid phone/email, or negative values | 422 Unprocessable Entity |
| `NotFoundException` | Raised when an entity ID is missing in the database | 404 Not Found |
| `ConflictException` | Raised on unique constraint violations (duplicate barcode, username, batch) | 409 Conflict |
| `InsufficientStockError` | Raised when POS sale quantity exceeds sellable non-expired stock | 400 Bad Request |
| `ExpiredBatchError` | Raised when an expired batch is selected for dispensing | 400 Bad Request |

---

## 2. Domain Services Reference

### 2.1 `AuthService` (`app/services/auth_service.py`)
Handles staff authentication, direct `bcrypt` hashing, user lifecycle, and role validation.
- `authenticate(identifier: str, password: str, ip_address: str = "127.0.0.1") -> Dict[str, Any]`
- `change_password(user_id: int, old_password: str, new_password: str) -> None`
- `admin_reset_password(current_user: Dict[str, Any], user_id: int, new_password: str) -> None`
- `create_user(current_user: Dict[str, Any], username: str, email: str, password: str, full_name: str, role: str, phone: Optional[str]) -> Dict[str, Any]`
- `toggle_user_status(current_user: Dict[str, Any], user_id: int) -> bool`
- `list_users() -> List[Dict[str, Any]]`

### 2.2 `CategoryService` (`app/services/category_service.py`)
Manages therapeutic medicine categories.
- `list_categories(search: Optional[str]) -> List[Dict[str, Any]]`
- `create_category(current_user: Dict[str, Any], name: str, description: Optional[str]) -> Dict[str, Any]`
- `update_category(current_user: Dict[str, Any], category_id: int, name: str, description: Optional[str]) -> Dict[str, Any]`
- `delete_category(current_user: Dict[str, Any], category_id: int) -> None`

### 2.3 `MedicineService` (`app/services/medicine_service.py`)
Manages medicine master catalog and calculates live available stock across non-expired batches.
- `list_medicines(category_id: Optional[int], search: Optional[str]) -> List[Dict[str, Any]]`
- `get_medicine(medicine_id: int) -> Dict[str, Any]`
- `create_medicine(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]`
- `update_medicine(current_user: Dict[str, Any], medicine_id: int, data: Dict[str, Any]) -> Dict[str, Any]`
- `delete_medicine(current_user: Dict[str, Any], medicine_id: int) -> None`

### 2.4 `BatchService` (`app/services/batch_service.py`)
Maintains batch-level physical inventory with expiration dates.
- `list_batches(medicine_id: Optional[int], search: Optional[str], status_filter: Optional[str]) -> List[Dict[str, Any]]`
- `get_available_batches_for_sale(medicine_id: int) -> List[Dict[str, Any]]` *(Applies FEFO sorting: `expiry_date >= today` ordered ascending)*
- `create_batch(current_user: Dict[str, Any], medicine_id: int, batch_no: str, expiry_date_val: date, quantity: int, purchase_price: float) -> Dict[str, Any]`
- `update_batch(current_user: Dict[str, Any], batch_id: int, data: Dict[str, Any]) -> Dict[str, Any]`
- `delete_batch(current_user: Dict[str, Any], batch_id: int) -> None`

### 2.5 `InventoryService` (`app/services/inventory_service.py`)
Monitors stock expiration windows and replenishment thresholds.
- `get_expiry_overview(warning_days: Optional[int]) -> Dict[str, Any]` *(Categorizes into Expired, Expiring Soon, Safe)*
- `get_low_stock_overview() -> Dict[str, Any]` *(Calculates replenishment deficit for stock <= min_stock)*
- `quarantine_and_discard_batch(current_user: Dict[str, Any], batch_id: int, reason: str) -> Dict[str, Any]`
- `update_medicine_min_stock(current_user: Dict[str, Any], medicine_id: int, new_min_stock: int) -> None`

### 2.6 `SupplierService` (`app/services/supplier_service.py`)
Maintains wholesale drug distributor profiles and transaction records.
- `list_suppliers(search: Optional[str]) -> List[Dict[str, Any]]`
- `get_supplier(supplier_id: int) -> Dict[str, Any]`
- `create_supplier(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]`
- `update_supplier(current_user: Dict[str, Any], supplier_id: int, data: Dict[str, Any]) -> Dict[str, Any]`
- `delete_supplier(current_user: Dict[str, Any], supplier_id: int) -> None`

### 2.7 `PurchaseService` (`app/services/purchase_service.py`)
Handles procurement orders and automatic batch intake.
- `list_purchases(supplier_id: Optional[int], search: Optional[str]) -> List[Dict[str, Any]]`
- `get_purchase(purchase_id: int) -> Dict[str, Any]`
- `create_purchase_order(current_user: Dict[str, Any], supplier_id: int, invoice_no: str, purchase_date_val: date, items: List[Dict[str, Any]], notes: Optional[str]) -> Dict[str, Any]` *(Automatically creates new batch or increments existing batch)*

### 2.8 `CustomerService` (`app/services/customer_service.py`)
Maintains patient CRM and billing history.
- `list_customers(search: Optional[str]) -> List[Dict[str, Any]]`
- `get_customer(customer_id: int) -> Dict[str, Any]`
- `create_customer(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]`
- `update_customer(current_user: Dict[str, Any], customer_id: int, data: Dict[str, Any]) -> Dict[str, Any]`
- `delete_customer(current_user: Dict[str, Any], customer_id: int) -> None`

### 2.9 `PrescriptionService` (`app/services/prescription_service.py`)
Tracks doctor prescriptions required for Schedule H compliance.
- `list_prescriptions(customer_id: Optional[int], search: Optional[str]) -> List[Dict[str, Any]]`
- `get_prescription(prescription_id: int) -> Dict[str, Any]`
- `create_prescription(current_user: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]`
- `delete_prescription(current_user: Dict[str, Any], prescription_id: int) -> None`

### 2.10 `SaleService` (`app/services/sale_service.py`)
Executes atomic POS checkouts with statutory checks and FEFO batch deduction.
- `generate_next_invoice_number() -> str`
- `create_sale(current_user: Dict[str, Any], cart_items: List[Dict[str, Any]], customer_id: Optional[int], prescription_id: Optional[int], payment_method: str, discount_percent: float, tax_percent: float, notes: Optional[str]) -> Dict[str, Any]`
- `list_sales(start_date: Optional[date], end_date: Optional[date], customer_id: Optional[int], payment_method: Optional[str], search: Optional[str], limit: int) -> List[Dict[str, Any]]`
- `get_sale(sale_id: int) -> Dict[str, Any]`

### 2.11 `DashboardService` (`app/services/dashboard_service.py`)
Aggregates real-time business KPIs and chart datasets.
- `get_kpis() -> Dict[str, Any]`
- `get_sales_timeline(days: int = 30) -> List[Dict[str, Any]]`
- `get_stock_by_category() -> List[Dict[str, Any]]`
- `get_top_selling_medicines(limit: int = 5, days: int = 30) -> List[Dict[str, Any]]`
- `get_recent_sales(limit: int = 6) -> List[Dict[str, Any]]`
- `get_urgent_alerts() -> Dict[str, List[Dict[str, Any]]]`

### 2.12 `NotificationService` (`app/services/notification_service.py`)
Automates background inventory warnings and event alerts.
- `sync_inventory_alerts() -> int` *(Deduplicated scan for expired batches, near-expiry ≤ 30d, low stock)*
- `get_unread_count() -> int`
- `get_notifications(is_read: Optional[bool], severity: Optional[str], limit: int) -> List[Dict[str, Any]]`
- `mark_as_read(notification_id: int) -> None`
- `mark_all_as_read() -> int`
- `clear_read_notifications() -> int`
- `create_notification(title: str, message: str, severity: str, notif_type: str) -> Dict[str, Any]`

### 2.13 `SettingService` & `BackupService` (`app/services/setting_service.py`, `app/services/backup_service.py`)
Manages hospital configuration and SQLite snapshot creation.
- `SettingService.get_all_settings() -> Dict[str, str]`
- `SettingService.update_settings(current_user: Dict[str, Any], settings_data: Dict[str, str]) -> Dict[str, str]`
- `BackupService.get_database_statistics() -> Dict[str, Any]`
- `BackupService.create_database_backup(current_user: Dict[str, Any]) -> Tuple[bytes, str]`
- `BackupService.restore_database_backup(current_user: Dict[str, Any], backup_bytes: bytes) -> bool`
