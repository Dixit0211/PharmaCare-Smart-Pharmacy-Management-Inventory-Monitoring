"""Dashboard analytics and KPI aggregation service."""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_, or_, desc
from app.core.database import get_db
from app.models.medicine import Medicine, MedicineBatch
from app.models.category import Category
from app.models.sale import Sale, SaleItem
from app.models.customer import Customer
from app.models.prescription import Prescription
from app.models.user import User
from app.core.logging import get_logger

logger = get_logger(__name__)


class DashboardService:
    """Aggregates real-time business performance, inventory status, and sales metrics."""

    @staticmethod
    def get_kpis() -> Dict[str, Any]:
        """Fetch primary top-level pharmacy KPIs."""
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        near_expiry_threshold = today + timedelta(days=30)

        with get_db() as session:
            # 1. Total Medicines Catalog & Categories
            total_medicines = session.scalar(select(func.count(Medicine.id))) or 0
            total_categories = session.scalar(select(func.count(Category.id))) or 0

            # 2. Total Registered Customers
            total_customers = session.scalar(select(func.count(Customer.id))) or 0

            # 3. Total Prescriptions on record
            total_prescriptions = session.scalar(select(func.count(Prescription.id))) or 0

            # 4. Stock Aggregation & Expiry Metrics
            # Non-expired active stock
            active_stock_qty = session.scalar(
                select(func.coalesce(func.sum(MedicineBatch.quantity), 0)).where(
                    MedicineBatch.expiry_date >= today
                )
            ) or 0

            # Expiring soon batches (within 30 days and has stock > 0)
            expiring_soon_count = session.scalar(
                select(func.count(MedicineBatch.id)).where(
                    and_(
                        MedicineBatch.expiry_date >= today,
                        MedicineBatch.expiry_date <= near_expiry_threshold,
                        MedicineBatch.quantity > 0,
                    )
                )
            ) or 0

            # Expired batches (past date and has stock > 0)
            expired_batches_count = session.scalar(
                select(func.count(MedicineBatch.id)).where(
                    and_(
                        MedicineBatch.expiry_date < today,
                        MedicineBatch.quantity > 0,
                    )
                )
            ) or 0

            # 5. Low stock medicines count
            med_rows = session.execute(
                select(
                    Medicine.id,
                    Medicine.min_stock,
                    func.coalesce(func.sum(MedicineBatch.quantity), 0).label("active_stock"),
                )
                .outerjoin(
                    MedicineBatch,
                    and_(
                        Medicine.id == MedicineBatch.medicine_id,
                        MedicineBatch.expiry_date >= today,
                    ),
                )
                .group_by(Medicine.id, Medicine.min_stock)
            ).all()

            low_stock_count = 0
            out_of_stock_count = 0
            adequate_stock_count = 0

            for row in med_rows:
                stk = row[2] or 0
                min_stk = row[1] or 0
                if stk == 0:
                    out_of_stock_count += 1
                    low_stock_count += 1
                elif stk <= min_stk:
                    low_stock_count += 1
                else:
                    adequate_stock_count += 1

            # 6. Today's Sales Performance
            today_sales = session.execute(
                select(
                    func.coalesce(func.sum(Sale.total_amount), 0.0).label("revenue"),
                    func.count(Sale.id).label("orders"),
                ).where(
                    and_(
                        Sale.sale_date >= today_start,
                        Sale.sale_date <= today_end,
                    )
                )
            ).one()

            today_revenue = float(today_sales.revenue or 0.0)
            today_orders = int(today_sales.orders or 0)

            return {
                "total_medicines": total_medicines,
                "total_categories": total_categories,
                "total_customers": total_customers,
                "total_prescriptions": total_prescriptions,
                "total_stock_units": active_stock_qty,
                "low_stock_count": low_stock_count,
                "out_of_stock_count": out_of_stock_count,
                "adequate_stock_count": adequate_stock_count,
                "expiring_soon_count": expiring_soon_count,
                "expired_batches_count": expired_batches_count,
                "today_revenue": today_revenue,
                "today_orders": today_orders,
            }

    @staticmethod
    def get_sales_timeline(days: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch daily sales aggregate for the last N days.
        Guarantees contiguous date records even if sales on a given day are zero.
        """
        today = date.today()
        start_date = today - timedelta(days=days - 1)
        start_datetime = datetime.combine(start_date, datetime.min.time())

        with get_db() as session:
            stmt = (
                select(
                    func.date(Sale.sale_date).label("sale_date"),
                    func.coalesce(func.sum(Sale.total_amount), 0.0).label("revenue"),
                    func.count(Sale.id).label("orders"),
                )
                .where(Sale.sale_date >= start_datetime)
                .group_by(func.date(Sale.sale_date))
                .order_by(func.date(Sale.sale_date).asc())
            )
            rows = session.execute(stmt).all()

            # Map existing results by date string
            sales_by_date = {
                str(r.sale_date): {
                    "revenue": round(float(r.revenue), 2),
                    "orders": int(r.orders),
                }
                for r in rows
            }

            # Build full contiguous timeline
            timeline = []
            for i in range(days):
                curr_d = start_date + timedelta(days=i)
                d_str = curr_d.strftime("%Y-%m-%d")
                day_data = sales_by_date.get(d_str, {"revenue": 0.0, "orders": 0})
                timeline.append(
                    {
                        "date": d_str,
                        "day_name": curr_d.strftime("%a, %d %b"),
                        "revenue": day_data["revenue"],
                        "orders": day_data["orders"],
                    }
                )

            return timeline

    @staticmethod
    def get_stock_by_category() -> List[Dict[str, Any]]:
        """Fetch non-expired stock units and medicine counts grouped by category."""
        today = date.today()
        with get_db() as session:
            stmt = (
                select(
                    Category.name.label("category_name"),
                    func.count(func.distinct(Medicine.id)).label("medicine_count"),
                    func.coalesce(func.sum(MedicineBatch.quantity), 0).label("total_stock"),
                )
                .join(Medicine, Category.id == Medicine.category_id)
                .outerjoin(
                    MedicineBatch,
                    and_(
                        Medicine.id == MedicineBatch.medicine_id,
                        MedicineBatch.expiry_date >= today,
                    ),
                )
                .group_by(Category.id, Category.name)
                .order_by(desc("total_stock"))
            )
            rows = session.execute(stmt).all()

            return [
                {
                    "category": r.category_name,
                    "medicine_count": int(r.medicine_count),
                    "total_stock": int(r.total_stock),
                }
                for r in rows
            ]

    @staticmethod
    def get_top_selling_medicines(limit: int = 5, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch top selling medicines by units sold and revenue within a period."""
        today = date.today()
        start_datetime = datetime.combine(today - timedelta(days=days), datetime.min.time())

        with get_db() as session:
            stmt = (
                select(
                    Medicine.name.label("medicine_name"),
                    Medicine.strength.label("strength"),
                    Category.name.label("category_name"),
                    func.sum(SaleItem.quantity).label("units_sold"),
                    func.sum(SaleItem.subtotal).label("total_revenue"),
                )
                .join(SaleItem, Medicine.id == SaleItem.medicine_id)
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Category, Medicine.category_id == Category.id)
                .where(Sale.sale_date >= start_datetime)
                .group_by(Medicine.id, Medicine.name, Medicine.strength, Category.name)
                .order_by(desc("units_sold"))
                .limit(limit)
            )
            rows = session.execute(stmt).all()

            return [
                {
                    "medicine": f"{r.medicine_name} ({r.strength})",
                    "category": r.category_name,
                    "units_sold": int(r.units_sold or 0),
                    "revenue": round(float(r.total_revenue or 0.0), 2),
                }
                for r in rows
            ]

    @staticmethod
    def get_recent_sales(limit: int = 6) -> List[Dict[str, Any]]:
        """Fetch the most recent completed sales transactions."""
        with get_db() as session:
            stmt = (
                select(
                    Sale,
                    Customer.name.label("customer_name"),
                    User.full_name.label("cashier_name"),
                    func.count(SaleItem.id).label("items_count"),
                )
                .outerjoin(Customer, Sale.customer_id == Customer.id)
                .join(User, Sale.user_id == User.id)
                .outerjoin(SaleItem, Sale.id == SaleItem.sale_id)
                .group_by(Sale.id)
                .order_by(Sale.sale_date.desc(), Sale.id.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).all()

            results = []
            for s, c_name, u_name, it_count in rows:
                results.append(
                    {
                        "id": s.id,
                        "invoice_no": s.invoice_no,
                        "customer": c_name or "Walk-in Customer",
                        "created_at": s.sale_date.strftime("%b %d, %I:%M %p") if s.sale_date else "",
                        "items_count": int(it_count or 0),
                        "total_amount": s.total_amount,
                        "payment_mode": s.payment_method.upper() if s.payment_method else "CASH",
                        "cashier": u_name or "Staff",
                    }
                )
            return results

    @staticmethod
    def get_urgent_alerts() -> Dict[str, List[Dict[str, Any]]]:
        """Fetch urgent low-stock and near-expiry action items for quick response."""
        today = date.today()
        near_expiry_date = today + timedelta(days=30)

        with get_db() as session:
            # Urgent near-expiry batches
            exp_stmt = (
                select(
                    MedicineBatch,
                    Medicine.name.label("medicine_name"),
                    Medicine.strength.label("strength"),
                )
                .join(Medicine, MedicineBatch.medicine_id == Medicine.id)
                .where(
                    and_(
                        MedicineBatch.expiry_date >= today,
                        MedicineBatch.expiry_date <= near_expiry_date,
                        MedicineBatch.quantity > 0,
                    )
                )
                .order_by(MedicineBatch.expiry_date.asc())
                .limit(4)
            )
            exp_rows = session.execute(exp_stmt).all()
            exp_alerts = []
            for b, med_name, strength in exp_rows:
                days_left = (b.expiry_date - today).days
                exp_alerts.append(
                    {
                        "batch_id": b.id,
                        "medicine": f"{med_name} ({strength})",
                        "batch_no": b.batch_no,
                        "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
                        "days_remaining": days_left,
                        "quantity": b.quantity,
                        "urgency": "High" if days_left <= 15 else "Medium",
                    }
                )

            # Urgent low stock medicines
            low_stmt = (
                select(
                    Medicine.id,
                    Medicine.name,
                    Medicine.strength,
                    Medicine.min_stock,
                    func.coalesce(func.sum(MedicineBatch.quantity), 0).label("stock"),
                )
                .outerjoin(
                    MedicineBatch,
                    and_(
                        Medicine.id == MedicineBatch.medicine_id,
                        MedicineBatch.expiry_date >= today,
                    ),
                )
                .group_by(Medicine.id, Medicine.name, Medicine.strength, Medicine.min_stock)
                .having(func.coalesce(func.sum(MedicineBatch.quantity), 0) <= Medicine.min_stock)
                .order_by(func.coalesce(func.sum(MedicineBatch.quantity), 0).asc())
                .limit(4)
            )
            low_rows = session.execute(low_stmt).all()
            low_alerts = []
            for r in low_rows:
                low_alerts.append(
                    {
                        "medicine_id": r.id,
                        "medicine": f"{r.name} ({r.strength})",
                        "current_stock": int(r.stock),
                        "min_stock": int(r.min_stock),
                        "deficit": max(0, int(r.min_stock) - int(r.stock)),
                    }
                )

            return {
                "near_expiry": exp_alerts,
                "low_stock": low_alerts,
            }
