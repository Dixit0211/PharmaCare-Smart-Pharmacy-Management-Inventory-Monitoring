"""Comprehensive pharmacy reporting, valuation analysis, and PDF/CSV export engine."""

import io
import csv
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_, desc
from app.core.database import get_db
from app.models.medicine import Medicine, MedicineBatch
from app.models.category import Category
from app.models.sale import Sale, SaleItem
from app.models.customer import Customer
from app.models.user import User
from app.models.setting import AppSetting
from app.services.setting_service import SettingService
from app.core.logging import get_logger

# ReportLab PDF imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = get_logger(__name__)


class ReportService:
    """Generates financial sales reports, profit margin analytics, and inventory valuations."""

    @staticmethod
    def get_sales_report(start_date: date, end_date: date) -> Dict[str, Any]:
        """Generate comprehensive sales and revenue summary for a date range."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        with get_db() as session:
            # Aggregate overall metrics
            agg_stmt = (
                select(
                    func.count(Sale.id).label("total_invoices"),
                    func.coalesce(func.sum(Sale.subtotal), 0.0).label("gross_sales"),
                    func.coalesce(func.sum(Sale.discount), 0.0).label("total_discount"),
                    func.coalesce(func.sum(Sale.tax), 0.0).label("total_tax"),
                    func.coalesce(func.sum(Sale.total_amount), 0.0).label("net_sales"),
                )
                .where(
                    and_(
                        Sale.sale_date >= start_dt,
                        Sale.sale_date <= end_dt,
                    )
                )
            )
            agg_res = session.execute(agg_stmt).one()

            total_invoices = int(agg_res.total_invoices or 0)
            gross_sales = float(agg_res.gross_sales or 0.0)
            total_discount = float(agg_res.total_discount or 0.0)
            total_tax = float(agg_res.total_tax or 0.0)
            net_sales = float(agg_res.net_sales or 0.0)
            avg_order_value = round(net_sales / total_invoices, 2) if total_invoices > 0 else 0.0

            # Compute estimated total profit
            profit_stmt = (
                select(
                    func.coalesce(
                        func.sum(SaleItem.subtotal - (SaleItem.quantity * SaleItem.purchase_price)),
                        0.0,
                    )
                )
                .join(Sale, SaleItem.sale_id == Sale.id)
                .where(
                    and_(
                        Sale.sale_date >= start_dt,
                        Sale.sale_date <= end_dt,
                    )
                )
            )
            total_profit = float(session.scalar(profit_stmt) or 0.0) - total_discount

            # Daily breakdown table
            daily_stmt = (
                select(
                    func.date(Sale.sale_date).label("sale_date"),
                    func.count(Sale.id).label("invoices_count"),
                    func.coalesce(func.sum(Sale.subtotal), 0.0).label("subtotal"),
                    func.coalesce(func.sum(Sale.discount), 0.0).label("discount"),
                    func.coalesce(func.sum(Sale.tax), 0.0).label("tax"),
                    func.coalesce(func.sum(Sale.total_amount), 0.0).label("net_revenue"),
                )
                .where(
                    and_(
                        Sale.sale_date >= start_dt,
                        Sale.sale_date <= end_dt,
                    )
                )
                .group_by(func.date(Sale.sale_date))
                .order_by(desc("sale_date"))
            )
            daily_rows = session.execute(daily_stmt).all()

            daily_records = [
                {
                    "date": str(r.sale_date),
                    "invoices": int(r.invoices_count),
                    "gross_sales": round(float(r.subtotal), 2),
                    "discount": round(float(r.discount), 2),
                    "tax": round(float(r.tax), 2),
                    "net_revenue": round(float(r.net_revenue), 2),
                }
                for r in daily_rows
            ]

            return {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "total_invoices": total_invoices,
                "gross_sales": round(gross_sales, 2),
                "total_discount": round(total_discount, 2),
                "total_tax": round(total_tax, 2),
                "net_sales": round(net_sales, 2),
                "total_profit": round(total_profit, 2),
                "avg_order_value": avg_order_value,
                "daily_breakdown": daily_records,
            }

    @staticmethod
    def get_profit_margin_report(start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Compute item-wise sales volume, revenue, historical cost, and profit margins."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        with get_db() as session:
            stmt = (
                select(
                    Medicine.name.label("medicine_name"),
                    Medicine.strength.label("strength"),
                    Category.name.label("category_name"),
                    func.sum(SaleItem.quantity).label("units_sold"),
                    func.sum(SaleItem.quantity * SaleItem.purchase_price).label("total_cost"),
                    func.sum(SaleItem.subtotal).label("total_revenue"),
                    func.sum(SaleItem.subtotal - (SaleItem.quantity * SaleItem.purchase_price)).label("net_profit"),
                )
                .join(SaleItem, Medicine.id == SaleItem.medicine_id)
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Category, Medicine.category_id == Category.id)
                .where(
                    and_(
                        Sale.sale_date >= start_dt,
                        Sale.sale_date <= end_dt,
                    )
                )
                .group_by(Medicine.id, Medicine.name, Medicine.strength, Category.name)
                .order_by(desc("net_profit"))
            )
            rows = session.execute(stmt).all()

            results = []
            for r in rows:
                rev = float(r.total_revenue or 0.0)
                cost = float(r.total_cost or 0.0)
                profit = float(r.net_profit or 0.0)
                margin_pct = round((profit / rev) * 100, 1) if rev > 0 else 0.0

                results.append(
                    {
                        "medicine": f"{r.medicine_name} ({r.strength})",
                        "category": r.category_name,
                        "units_sold": int(r.units_sold or 0),
                        "total_cost": round(cost, 2),
                        "total_revenue": round(rev, 2),
                        "net_profit": round(profit, 2),
                        "margin_percent": margin_pct,
                    }
                )
            return results

    @staticmethod
    def get_inventory_valuation_report() -> Dict[str, Any]:
        """Compute live physical inventory valuation at purchase cost vs retail MRP."""
        today = date.today()
        with get_db() as session:
            stmt = (
                select(
                    Medicine.name.label("medicine_name"),
                    Medicine.strength.label("strength"),
                    Category.name.label("category_name"),
                    Medicine.dosage_form.label("dosage_form"),
                    Medicine.min_stock.label("min_stock"),
                    func.coalesce(func.sum(MedicineBatch.quantity), 0).label("active_stock"),
                    func.coalesce(func.sum(MedicineBatch.quantity * MedicineBatch.purchase_price), 0.0).label("valuation_cost"),
                    func.coalesce(func.sum(MedicineBatch.quantity * Medicine.selling_price), 0.0).label("valuation_retail"),
                )
                .join(Category, Medicine.category_id == Category.id)
                .outerjoin(
                    MedicineBatch,
                    and_(
                        Medicine.id == MedicineBatch.medicine_id,
                        MedicineBatch.expiry_date >= today,
                    ),
                )
                .group_by(
                    Medicine.id,
                    Medicine.name,
                    Medicine.strength,
                    Category.name,
                    Medicine.dosage_form,
                    Medicine.min_stock,
                    Medicine.selling_price,
                )


                .order_by(desc("valuation_cost"))
            )
            rows = session.execute(stmt).all()

            items = []
            total_stock_units = 0
            total_valuation_cost = 0.0
            total_valuation_retail = 0.0

            for r in rows:
                stock = int(r.active_stock or 0)
                cost_val = float(r.valuation_cost or 0.0)
                ret_val = float(r.valuation_retail or 0.0)
                unrealized_profit = ret_val - cost_val

                total_stock_units += stock
                total_valuation_cost += cost_val
                total_valuation_retail += ret_val

                items.append(
                    {
                        "medicine": f"{r.medicine_name} ({r.strength})",
                        "category": r.category_name,
                        "dosage_form": r.dosage_form,
                        "active_stock": stock,
                        "min_stock": int(r.min_stock),
                        "cost_valuation": round(cost_val, 2),
                        "retail_valuation": round(ret_val, 2),
                        "unrealized_profit": round(unrealized_profit, 2),
                    }
                )

            return {
                "total_units": total_stock_units,
                "total_cost_value": round(total_valuation_cost, 2),
                "total_retail_value": round(total_valuation_retail, 2),
                "total_potential_margin": round(total_valuation_retail - total_valuation_cost, 2),
                "items": items,
            }

    @staticmethod
    def get_expiry_risk_report() -> Dict[str, Any]:
        """Detailed financial audit of expired loss and near-expiry at-risk stock."""
        today = date.today()
        near_expiry_threshold = today + timedelta(days=30)

        with get_db() as session:
            stmt = (
                select(
                    MedicineBatch,
                    Medicine.name.label("medicine_name"),
                    Medicine.strength.label("strength"),
                    Category.name.label("category_name"),
                )
                .join(Medicine, MedicineBatch.medicine_id == Medicine.id)
                .join(Category, Medicine.category_id == Category.id)
                .where(MedicineBatch.quantity > 0)
                .order_by(MedicineBatch.expiry_date.asc())
            )
            rows = session.execute(stmt).all()

            expired_list = []
            near_expiry_list = []
            total_expired_loss = 0.0
            total_at_risk_value = 0.0

            for b, med_name, strength, cat_name in rows:
                loss_val = round(b.quantity * b.purchase_price, 2)
                days_left = (b.expiry_date - today).days

                item = {
                    "medicine": f"{med_name} ({strength})",
                    "category": cat_name,
                    "batch_no": b.batch_no,
                    "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
                    "days_remaining": days_left,
                    "quantity": b.quantity,
                    "purchase_price": b.purchase_price,
                    "financial_value": loss_val,
                }

                if b.expiry_date < today:
                    item["status"] = "EXPIRED (Quarantined)"
                    expired_list.append(item)
                    total_expired_loss += loss_val
                elif b.expiry_date <= near_expiry_threshold:
                    item["status"] = "NEAR EXPIRY (<30d)"
                    near_expiry_list.append(item)
                    total_at_risk_value += loss_val

            return {
                "total_expired_loss": round(total_expired_loss, 2),
                "total_at_risk_value": round(total_at_risk_value, 2),
                "expired_count": len(expired_list),
                "near_expiry_count": len(near_expiry_list),
                "expired_batches": expired_list,
                "near_expiry_batches": near_expiry_list,
            }

    @staticmethod
    def export_to_csv(data: List[Dict[str, Any]], fieldnames: List[str]) -> str:
        """Convert a list of dictionaries into a clean CSV string."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def generate_sales_report_pdf(report_data: Dict[str, Any]) -> bytes:
        """Generate a professional executive sales & revenue report in PDF."""
        settings = SettingService.get_all_settings()
        pharmacy_name = settings.get("pharmacy_name", "PharmaCare Hospital Pharmacy")
        pharmacy_addr = settings.get("pharmacy_address", "Metro City")
        pharmacy_dl = settings.get("pharmacy_dl_no", "DL-99881")
        pharmacy_gstin = settings.get("pharmacy_gstin", "27AAAAA0000A1Z5")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748B"),
        )
        header_cell_style = ParagraphStyle(
            "HeaderCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        )
        cell_style = ParagraphStyle(
            "BodyCell",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1E293B"),
        )

        story = []

        # 1. Header & Pharmacy Info
        story.append(Paragraph(f"<b>{pharmacy_name}</b>", title_style))
        story.append(Paragraph(f"{pharmacy_addr} | DL: {pharmacy_dl} | GSTIN: {pharmacy_gstin}", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0D9488"), spaceAfter=15))

        # 2. Report Title & Date Scope
        story.append(Paragraph("<b>EXECUTIVE SALES & REVENUE REPORT</b>", ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=16, textColor=colors.HexColor("#0D9488"))))
        story.append(Paragraph(f"Reporting Period: <b>{report_data['start_date']}</b> to <b>{report_data['end_date']}</b> | Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
        story.append(Spacer(1, 12))

        # 3. Summary Metric Matrix Table
        summary_data = [
            [
                Paragraph("<b>Total Invoices:</b>", cell_style),
                Paragraph(str(report_data["total_invoices"]), cell_style),
                Paragraph("<b>Gross Sales:</b>", cell_style),
                Paragraph(f"₹{report_data['gross_sales']:,.2f}", cell_style),
            ],
            [
                Paragraph("<b>Total Discounts:</b>", cell_style),
                Paragraph(f"₹{report_data['total_discount']:,.2f}", cell_style),
                Paragraph("<b>Total GST Collected:</b>", cell_style),
                Paragraph(f"₹{report_data['total_tax']:,.2f}", cell_style),
            ],
            [
                Paragraph("<b>Net Realized Sales:</b>", cell_style),
                Paragraph(f"<b>₹{report_data['net_sales']:,.2f}</b>", cell_style),
                Paragraph("<b>Estimated Net Profit:</b>", cell_style),
                Paragraph(f"<b>₹{report_data['total_profit']:,.2f}</b>", cell_style),
            ],
        ]
        sum_table = Table(summary_data, colWidths=[1.5 * inch, 1.8 * inch, 1.5 * inch, 1.8 * inch])
        sum_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(sum_table)
        story.append(Spacer(1, 16))

        # 4. Daily Breakdown Table
        story.append(Paragraph("<b>Daily Revenue Breakdown</b>", ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, leading=14, textColor=colors.HexColor("#0F172A"))))
        story.append(Spacer(1, 6))

        daily_table_data = [[
            Paragraph("Date", header_cell_style),
            Paragraph("Invoices", header_cell_style),
            Paragraph("Gross (₹)", header_cell_style),
            Paragraph("Discount (₹)", header_cell_style),
            Paragraph("Tax (₹)", header_cell_style),
            Paragraph("Net Revenue (₹)", header_cell_style),
        ]]

        for r in report_data.get("daily_breakdown", [])[:25]:
            daily_table_data.append([
                Paragraph(r["date"], cell_style),
                Paragraph(str(r["invoices"]), cell_style),
                Paragraph(f"₹{r['gross_sales']:,.2f}", cell_style),
                Paragraph(f"₹{r['discount']:,.2f}", cell_style),
                Paragraph(f"₹{r['tax']:,.2f}", cell_style),
                Paragraph(f"<b>₹{r['net_revenue']:,.2f}</b>", cell_style),
            ])

        table_daily = Table(daily_table_data, colWidths=[1.3 * inch, 0.9 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch, 1.2 * inch])
        table_daily.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ])
        )
        story.append(table_daily)
        story.append(Spacer(1, 20))

        # 5. Footer & Signoff
        story.append(Paragraph("<i>This is a computer-generated official compliance and financial summary document.</i>", subtitle_style))

        doc.build(story)
        return buffer.getvalue()
