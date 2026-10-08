"""Comprehensive pharmacy reporting, profit analytics, inventory valuation, and exports page."""

from datetime import date, timedelta
import streamlit as st
import pandas as pd
from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.services.report_service import ReportService
from app.services.notification_service import NotificationService
from app.utils.formatters import format_currency

if not is_authenticated():
    st.warning("Please log in to access the pharmacy management system.")
    st.stop()

inject_custom_styles()

try:
    unread_alerts_count = NotificationService.get_unread_count()
except Exception:
    unread_alerts_count = 0

render_sidebar(unread_notifications_count=unread_alerts_count)

st.markdown("## :material/analytics: Pharmacy Reports & Export Engine")
st.caption("Generate financial sales statements, itemized profit margins, live inventory valuations, and statutory loss audits")

tab_sales, tab_profit, tab_valuation, tab_expiry = st.tabs([
    ":material/receipt_long: Sales & Revenue",
    ":material/trending_up: Profit Margins",
    ":material/inventory: Inventory Valuation",
    ":material/event_busy: Expiry & Loss Audit",
])

today = date.today()

# -------------------------------------------------------------
# TAB 1: Sales & Revenue Report
# -------------------------------------------------------------
with tab_sales:
    st.markdown("### Financial Sales & Invoicing Report")
    
    col_date1, col_date2, col_quick = st.columns([1.2, 1.2, 2.0])
    with col_date1:
        start_d = st.date_input("Start Date", value=today - timedelta(days=30), key="sales_start_d")
    with col_date2:
        end_d = st.date_input("End Date", value=today, key="sales_end_d")
    with col_quick:
        st.markdown("<label style='font-size:0.85rem; color:#64748B;'>Quick Date Range</label>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        with q1:
            if st.button("Today", use_container_width=True):
                st.session_state["sales_start_d"] = today
                st.session_state["sales_end_d"] = today
                st.rerun()
        with q2:
            if st.button("Last 7 Days", use_container_width=True):
                st.session_state["sales_start_d"] = today - timedelta(days=7)
                st.session_state["sales_end_d"] = today
                st.rerun()
        with q3:
            if st.button("Last 30 Days", use_container_width=True):
                st.session_state["sales_start_d"] = today - timedelta(days=30)
                st.session_state["sales_end_d"] = today
                st.rerun()

    if start_d > end_d:
        st.error("Start date cannot be after end date.")
    else:
        sales_rep = ReportService.get_sales_report(start_d, end_d)

        # KPI Summary Matrix
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_metric_card("Net Realized Sales", format_currency(sales_rep["net_sales"]), f"{sales_rep['total_invoices']} orders billed", accent="teal", icon="💰")
        with m2:
            render_metric_card("Gross Invoiced", format_currency(sales_rep["gross_sales"]), f"Discounts: {format_currency(sales_rep['total_discount'])}", accent="blue", icon="🧾")
        with m3:
            render_metric_card("GST Tax Collected", format_currency(sales_rep["total_tax"]), "Statutory tax component", accent="amber", icon="🏛️")
        with m4:
            render_metric_card("Estimated Net Profit", format_currency(sales_rep["total_profit"]), f"Avg order: {format_currency(sales_rep['avg_order_value'])}", accent="green", icon="📈")

        st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

        # Export Controls
        c_exp1, c_exp2, _ = st.columns([1.2, 1.4, 2.5])
        with c_exp1:
            csv_data = ReportService.export_to_csv(
                sales_rep["daily_breakdown"],
                fieldnames=["date", "invoices", "gross_sales", "discount", "tax", "net_revenue"],
            )
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=f"pharmacare_sales_report_{start_d}_to_{end_d}.csv",
                mime="text/csv",
                icon=":material/download:",
                use_container_width=True,
            )
        with c_exp2:
            try:
                pdf_bytes = ReportService.generate_sales_report_pdf(sales_rep)
                st.download_button(
                    label="Download Official PDF Report",
                    data=pdf_bytes,
                    file_name=f"pharmacare_executive_report_{start_d}_to_{end_d}.pdf",
                    mime="application/pdf",
                    icon=":material/picture_as_pdf:",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"PDF generation error: {e}")

        # Daily Table
        st.markdown("##### Daily Revenue Breakdown")
        if sales_rep["daily_breakdown"]:
            df_daily = pd.DataFrame(sales_rep["daily_breakdown"])
            df_daily.columns = ["Sale Date", "Invoices", "Gross Subtotal (₹)", "Discount (₹)", "Tax GST (₹)", "Net Revenue (₹)"]
            st.dataframe(df_daily, use_container_width=True, hide_index=True)
        else:
            render_empty_state("No Sales Found", "No sales transactions were recorded in this date range.", icon="📊")

# -------------------------------------------------------------
# TAB 2: Profit Margin Analysis
# -------------------------------------------------------------
with tab_profit:
    st.markdown("### Itemized Profitability & Product Margins")
    
    col_p1, col_p2 = st.columns([1.2, 1.2])
    with col_p1:
        p_start_d = st.date_input("Start Date", value=today - timedelta(days=30), key="profit_start_d")
    with col_p2:
        p_end_d = st.date_input("End Date", value=today, key="profit_end_d")

    profit_items = ReportService.get_profit_margin_report(p_start_d, p_end_d)

    if profit_items:
        # Summary
        tot_profit = sum(item["net_profit"] for item in profit_items)
        tot_revenue = sum(item["total_revenue"] for item in profit_items)
        tot_units = sum(item["units_sold"] for item in profit_items)
        overall_margin = round((tot_profit / tot_revenue) * 100, 1) if tot_revenue > 0 else 0.0

        p1, p2, p3 = st.columns(3)
        with p1:
            render_metric_card("Total Product Profit", format_currency(tot_profit), f"{tot_units} units dispensed", accent="green", icon="💵")
        with p2:
            render_metric_card("Total Dispensed Revenue", format_currency(tot_revenue), f"Cost: {format_currency(tot_revenue - tot_profit)}", accent="teal", icon="📦")
        with p3:
            render_metric_card("Overall Margin %", f"{overall_margin}%", "Weighted return on sales", accent="blue", icon="📊")

        st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

        # CSV Download
        csv_profit = ReportService.export_to_csv(
            profit_items,
            fieldnames=["medicine", "category", "units_sold", "total_cost", "total_revenue", "net_profit", "margin_percent"],
        )
        st.download_button(
            label="Download Profitability CSV",
            data=csv_profit,
            file_name=f"pharmacare_profit_margins_{p_start_d}_to_{p_end_d}.csv",
            mime="text/csv",
            icon=":material/download:",
        )

        df_prof = pd.DataFrame(profit_items)
        df_prof.columns = ["Medicine", "Category", "Units Sold", "Total Cost (₹)", "Total Revenue (₹)", "Net Profit (₹)", "Margin %"]
        st.dataframe(df_prof, use_container_width=True, hide_index=True)
    else:
        render_empty_state("No Margin Data", "No items were sold during this period.", icon="📈")

# -------------------------------------------------------------
# TAB 3: Inventory Valuation
# -------------------------------------------------------------
with tab_valuation:
    st.markdown("### Live Inventory Valuation & Capital Investment")
    
    val_rep = ReportService.get_inventory_valuation_report()

    v1, v2, v3 = st.columns(3)
    with v1:
        render_metric_card("Stock Valuation (Purchase Cost)", format_currency(val_rep["total_cost_value"]), f"{val_rep['total_units']:,} physical units in stock", accent="teal", icon="🏭")
    with v2:
        render_metric_card("Stock Valuation (Retail MRP)", format_currency(val_rep["total_retail_value"]), "Potential retail realization", accent="blue", icon="🏪")
    with v3:
        render_metric_card("Unrealized Profit Margin", format_currency(val_rep["total_potential_margin"]), "Gross stock markup", accent="green", icon="✨")

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    csv_val = ReportService.export_to_csv(
        val_rep["items"],
        fieldnames=["medicine", "category", "dosage_form", "active_stock", "min_stock", "cost_valuation", "retail_valuation", "unrealized_profit"],
    )
    st.download_button(
        label="Download Inventory Valuation CSV",
        data=csv_val,
        file_name=f"pharmacare_inventory_valuation_{today}.csv",
        mime="text/csv",
        icon=":material/download:",
    )

    if val_rep["items"]:
        df_val = pd.DataFrame(val_rep["items"])
        df_val.columns = ["Medicine", "Category", "Form", "Stock Units", "Min Threshold", "Cost Value (₹)", "Retail Value (₹)", "Unrealized Profit (₹)"]
        st.dataframe(df_val, use_container_width=True, hide_index=True)
    else:
        render_empty_state("No Active Inventory", "Inventory catalog is currently empty.", icon="📦")

# -------------------------------------------------------------
# TAB 4: Expiry & Loss Audit
# -------------------------------------------------------------
with tab_expiry:
    st.markdown("### Expiry Loss Audit & Financial Risk Review")
    
    risk_rep = ReportService.get_expiry_risk_report()

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        render_metric_card("Quarantined Expired Loss", format_currency(risk_rep["total_expired_loss"]), f"{risk_rep['expired_count']} batches quarantined", accent="red", icon="⚠️")
    with e2:
        render_metric_card("At-Risk Stock (<30 Days)", format_currency(risk_rep["total_at_risk_value"]), f"{risk_rep['near_expiry_count']} batches near expiry", accent="amber", icon="⏳")
    with e3:
        render_metric_card("Total High-Risk Batches", str(risk_rep["expired_count"] + risk_rep["near_expiry_count"]), "Batches requiring action", accent="blue", icon="📋")
    with e4:
        render_metric_card("Total Risk Capital", format_currency(risk_rep["total_expired_loss"] + risk_rep["total_at_risk_value"]), "Total financial exposure", accent="red", icon="🚨")

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    col_exp_sec, col_near_sec = st.columns(2)

    with col_exp_sec:
        st.markdown("##### 🔴 Quarantined Expired Batches (Write-Off Loss)")
        if risk_rep["expired_batches"]:
            df_exp = pd.DataFrame(risk_rep["expired_batches"])
            df_exp = df_exp[["medicine", "batch_no", "expiry_date", "quantity", "financial_value"]]
            df_exp.columns = ["Medicine", "Batch", "Expiry Date", "Qty", "Loss (₹)"]
            st.dataframe(df_exp, use_container_width=True, hide_index=True)
        else:
            st.info("No expired batches found in quarantine.")

    with col_near_sec:
        st.markdown("##### 🟠 Near-Expiry Batches (<30 Days Risk)")
        if risk_rep["near_expiry_batches"]:
            df_near = pd.DataFrame(risk_rep["near_expiry_batches"])
            df_near = df_near[["medicine", "batch_no", "expiry_date", "days_remaining", "quantity", "financial_value"]]
            df_near.columns = ["Medicine", "Batch", "Expiry Date", "Days Left", "Qty", "Risk Value (₹)"]
            st.dataframe(df_near, use_container_width=True, hide_index=True)
        else:
            st.info("No near-expiry batches detected.")
