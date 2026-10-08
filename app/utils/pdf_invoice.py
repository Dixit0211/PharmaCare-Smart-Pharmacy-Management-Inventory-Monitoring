"""Hospital-grade PDF receipt and tax invoice generator using ReportLab."""

import io
from typing import Dict, Any, Optional
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.units import mm
from app.core.config import settings


def generate_invoice_pdf(sale_data: Dict[str, Any], pharmacy_info: Optional[Dict[str, str]] = None) -> bytes:
    """
    Generate professional clinical PDF invoice in bytes format.
    Accepts full sale dictionary and optional pharmacy metadata.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    info = pharmacy_info or {
        "name": "PharmaCare Central Pharmacy",
        "address": "104 Healthcare Boulevard, Medical District, City - 400001",
        "phone": "+91 98765 43210",
        "email": "contact@pharmacare.local",
        "gst": "27ABCDE1234F1Z5",
        "license": "DL-2024-MH-99482 / 21B",
    }

    styles = getSampleStyleSheet()
    
    # Custom Palette
    teal_primary = colors.HexColor("#0D9488")
    dark_navy = colors.HexColor("#0F172A")
    text_dark = colors.HexColor("#1E293B")
    gray_light = colors.HexColor("#F8FAFC")
    border_gray = colors.HexColor("#CBD5E1")

    # Typography styles
    style_header_title = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=dark_navy,
    )

    style_header_sub = ParagraphStyle(
        "HeaderSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )

    style_inv_title = ParagraphStyle(
        "InvTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        alignment=2,  # Right aligned
        textColor=teal_primary,
    )

    style_inv_meta = ParagraphStyle(
        "InvMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=2,
        textColor=text_dark,
    )

    style_cell = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=text_dark,
    )

    style_cell_bold = ParagraphStyle(
        "CellTextBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=text_dark,
    )

    style_th = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
    )

    story = []

    # 1. Header Row (Pharmacy Brand on Left, Tax Invoice Title on Right)
    pharmacy_header_html = f"""
    <b>{info['name']}</b><br/>
    {info['address']}<br/>
    Phone: {info['phone']} | Email: {info['email']}<br/>
    GSTIN: <b>{info['gst']}</b> | Drug Lic: <b>{info['license']}</b>
    """

    inv_meta_html = f"""
    TAX INVOICE<br/>
    <b>#{sale_data.get('invoice_no', 'INV-000')}</b><br/>
    Date: {sale_data.get('sale_date', datetime.now().strftime('%Y-%m-%d %H:%M'))}<br/>
    Payment: <b>{sale_data.get('payment_method', 'Cash')}</b>
    """

    header_table = Table(
        [
            [
                Paragraph(pharmacy_header_html, style_header_sub),
                Paragraph(inv_meta_html, style_inv_meta),
            ]
        ],
        colWidths=[110 * mm, 70 * mm],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=teal_primary, spaceBefore=2, spaceAfter=4 * mm))

    # 2. Patient & Cashier Details Box
    cust_name = sale_data.get("customer_name") or "Walk-in Retail Customer"
    cust_phone = sale_data.get("customer_phone") or "-"
    pharmacist_name = sale_data.get("pharmacist_name") or "Authorized Pharmacist"
    doctor_name = sale_data.get("doctor_name") or "N/A (Over the Counter)"

    meta_info_html_left = f"""
    <b>Billed To:</b> {cust_name}<br/>
    <b>Contact Phone:</b> {cust_phone}<br/>
    <b>Prescribing Doctor:</b> {doctor_name}
    """

    meta_info_html_right = f"""
    <b>Dispensed By:</b> {pharmacist_name}<br/>
    <b>POS Register:</b> Counter-01 (Main Pharmacy)<br/>
    <b>Status:</b> <font color="#0D9488">PAID / DISPENSED</font>
    """

    meta_table = Table(
        [
            [
                Paragraph(meta_info_html_left, style_cell),
                Paragraph(meta_info_html_right, style_cell),
            ]
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), gray_light),
            ("BOX", (0, 0), (-1, -1), 0.5, border_gray),
            ("PADDING", (0, 0), (-1, -1), 3 * mm),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # 3. Itemized Medicines Table
    items_header = [
        Paragraph("#", style_th),
        Paragraph("Medicine Description", style_th),
        Paragraph("Batch No", style_th),
        Paragraph("Expiry", style_th),
        Paragraph("Qty", style_th),
        Paragraph("Rate (₹)", style_th),
        Paragraph("Amount (₹)", style_th),
    ]

    items_data = [items_header]
    raw_items = sale_data.get("items", [])

    for idx, it in enumerate(raw_items, 1):
        items_data.append([
            Paragraph(str(idx), style_cell),
            Paragraph(it.get("medicine_name", "Medicine"), style_cell_bold),
            Paragraph(it.get("batch_no", "-"), style_cell),
            Paragraph(str(it.get("expiry_date", "-")), style_cell),
            Paragraph(str(it.get("quantity", 1)), style_cell),
            Paragraph(f"{float(it.get('unit_price', 0)):.2f}", style_cell),
            Paragraph(f"{float(it.get('subtotal', 0)):.2f}", style_cell_bold),
        ])

    items_table = Table(
        items_data,
        colWidths=[10 * mm, 62 * mm, 28 * mm, 25 * mm, 15 * mm, 20 * mm, 20 * mm],
    )
    items_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), teal_primary),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, gray_light]),
        ])
    )
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    # 4. Financial Calculations Summary
    subtotal = float(sale_data.get("subtotal", 0.0))
    discount = float(sale_data.get("discount", 0.0))
    tax = float(sale_data.get("tax", 0.0))
    total_amount = float(sale_data.get("total_amount", 0.0))

    totals_data = [
        [Paragraph("Items Subtotal:", style_cell), Paragraph(f"₹{subtotal:,.2f}", style_cell_bold)],
        [Paragraph("Discount Applied:", style_cell), Paragraph(f"- ₹{discount:,.2f}", style_cell)],
        [Paragraph("GST / Tax (5%):", style_cell), Paragraph(f"+ ₹{tax:,.2f}", style_cell)],
        [Paragraph("<b>NET PAYABLE:</b>", style_cell_bold), Paragraph(f"<b>₹{total_amount:,.2f}</b>", style_inv_title)],
    ]

    totals_table = Table(totals_data, colWidths=[130 * mm, 50 * mm])
    totals_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("LINEABOVE", (0, 3), (1, 3), 1, teal_primary),
        ])
    )
    story.append(totals_table)
    story.append(Spacer(1, 6 * mm))

    # 5. Terms & Legal Medical Disclaimer
    disclaimer_html = """
    <b>Terms & Conditions:</b><br/>
    1. Goods once sold cannot be returned without a valid prescription and batch seal verification.<br/>
    2. Store all pharmaceutical products in a cool, dry place below 25°C away from direct sunlight.<br/>
    3. This is a computer-generated tax invoice verified under Drug & Cosmetics Act standards.
    """
    story.append(HRFlowable(width="100%", thickness=0.5, color=border_gray, spaceBefore=2, spaceAfter=3 * mm))
    story.append(Paragraph(disclaimer_html, style_header_sub))

    # Build document
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
