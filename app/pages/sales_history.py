"""Sales History, Invoice Records, and PDF Reprint page."""

from datetime import date
from typing import Dict, Any
import streamlit as st
import pandas as pd

from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.components.status_badge import render_status_badge
from app.services.sale_service import SaleService
from app.utils.pdf_invoice import generate_invoice_pdf
from app.core.exceptions import AppException

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/receipt_long: Sales History & Invoices")
st.caption("Inspect past sales transactions, review dispensed batch lots, evaluate profit margins, and reprint tax invoices")

all_sales = SaleService.list_sales(limit=500)
total_invoices = len(all_sales)
total_revenue = sum(s["total_amount"] for s in all_sales)
avg_ticket = (total_revenue / total_invoices) if total_invoices > 0 else 0.0

k1, k2, k3 = st.columns(3)
with k1:
    render_metric_card("Total Completed Invoices", str(total_invoices), "Counter sales transactions", accent="teal", icon="🧾")
with k2:
    render_metric_card("Total Gross Revenue", f"₹{total_revenue:,.2f}", "Cumulative billing turnover", accent="green", icon="💰")
with k3:
    render_metric_card("Average Order Value", f"₹{avg_ticket:,.2f}", "Revenue per transaction", accent="blue", icon="📊")

st.markdown("---")

# Filter Controls
f1, f2 = st.columns([3, 2])
with f1:
    search_term = st.text_input("Search Invoices", placeholder="Search by invoice number, customer name...", label_visibility="collapsed")
with f2:
    selected_pm = st.selectbox("Payment Method", options=["All", "Cash", "UPI", "Card", "Net Banking", "Other"], label_visibility="collapsed")

sales_filtered = SaleService.list_sales(
    payment_method=selected_pm,
    search=search_term,
    limit=200,
)

if not sales_filtered:
    render_empty_state("No Sales Found", "No billing invoices match the specified criteria.")
else:
    s_table = []
    for s in sales_filtered:
        s_table.append({
            "Invoice No": s["invoice_no"],
            "Customer": s["customer_name"],
            "Date & Time": s["sale_date"],
            "Items": f"{s['item_count']} items",
            "Subtotal": f"₹{s['subtotal']:,.2f}",
            "Discount": f"- ₹{s['discount']:,.2f}",
            "Tax (GST)": f"+ ₹{s['tax']:,.2f}",
            "Total Amount": f"₹{s['total_amount']:,.2f}",
            "Payment": s["payment_method"],
            "Billed By": s["pharmacist_name"],
        })

    st.dataframe(pd.DataFrame(s_table), use_container_width=True, hide_index=True)

    st.markdown("### Invoice Detailed Breakdown & PDF Reprint")
    inv_choices = {f"{s['invoice_no']} - {s['customer_name']} (₹{s['total_amount']:,.2f})": s["id"] for s in sales_filtered}
    sel_inv_label = st.selectbox("Select invoice to inspect details & download PDF:", options=list(inv_choices.keys()))
    sel_inv_id = inv_choices[sel_inv_label]

    if sel_inv_id:
        sale_detail = SaleService.get_sale(sel_inv_id)
        with st.container(border=True):
            col_h1, col_h2, col_h3 = st.columns([2, 2, 2])
            with col_h1:
                st.markdown(f"#### Invoice: **{sale_detail['invoice_no']}**")
                st.caption(f"Date: **{sale_detail['sale_date']}**")
                st.write(f"👤 Patient: **{sale_detail['customer_name']}** (Phone: `{sale_detail['customer_phone']}`)")
            with col_h2:
                st.write(f"💳 Payment Method: **{sale_detail['payment_method']}**")
                st.write(f"🩺 Prescribing Doctor: **{sale_detail['doctor_name']}**")
                st.write(f"👨‍⚕️ Dispensing Pharmacist: **{sale_detail['pharmacist_name']}**")
            with col_h3:
                st.write(f"💰 Grand Total: **₹{sale_detail['total_amount']:,.2f}**")
                st.write(f"📈 Profit Margin: **₹{sale_detail['profit']:,.2f}**")
                render_status_badge("paid", "PAID & DISPENSED")

            st.markdown("##### Dispensed Batch Items in this Invoice:")
            items_table = []
            for it in sale_detail["items"]:
                items_table.append({
                    "Medicine Item": it["medicine_name"],
                    "Dispensed Batch No": it["batch_no"],
                    "Batch Expiry": it["expiry_date"],
                    "Quantity": f"{it['quantity']} units",
                    "Selling Price": f"₹{it['unit_price']:.2f}",
                    "Purchase Cost": f"₹{it['purchase_price']:.2f}",
                    "Subtotal": f"₹{it['subtotal']:,.2f}",
                    "Gross Profit": f"₹{it['profit']:,.2f}",
                })
            st.dataframe(pd.DataFrame(items_table), use_container_width=True, hide_index=True)

            st.markdown("---")
            pdf_bytes = generate_invoice_pdf(sale_detail)
            st.download_button(
                label=f"📄 Download Duplicate PDF Invoice ({sale_detail['invoice_no']})",
                data=pdf_bytes,
                file_name=f"{sale_detail['invoice_no']}.pdf",
                mime="application/pdf",
                icon=":material/download:",
                type="primary",
            )
