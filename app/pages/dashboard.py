"""Hospital pharmacy executive dashboard with real-time KPIs and Plotly analytics."""

from datetime import date
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.services.dashboard_service import DashboardService
from app.services.notification_service import NotificationService
from app.utils.formatters import format_currency

if not is_authenticated():
    st.warning("Please log in to access the pharmacy management system.")
    st.stop()

inject_custom_styles()

# Auto-sync inventory alerts in background for accurate badges
try:
    NotificationService.sync_inventory_alerts()
    unread_alerts_count = NotificationService.get_unread_count()
except Exception:
    unread_alerts_count = 0

render_sidebar(unread_notifications_count=unread_alerts_count)

user = get_current_user()

# Header
st.markdown("## :material/dashboard: Hospital Pharmacy Executive Dashboard")
st.caption(
    f"Welcome back, **{user.get('full_name', 'User')}** | Real-time clinical dispensing, stock health, and revenue analytics"
)

# Fetch Aggregated Data
kpis = DashboardService.get_kpis()
urgent_alerts = DashboardService.get_urgent_alerts()

# -------------------------------------------------------------
# 1. Top KPI Metric Grid
# -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1:
    render_metric_card(
        title="Today's Revenue",
        value=format_currency(kpis["today_revenue"]),
        subtext=f"{kpis['today_orders']} completed orders today",
        accent="teal",
        icon="💰",
    )

with c2:
    render_metric_card(
        title="Active Stock Units",
        value=f"{kpis['total_stock_units']:,}",
        subtext=f"Across {kpis['total_medicines']} catalog medicines",
        accent="green",
        icon="📦",
    )

with c3:
    exp_accent = "red" if kpis["expired_batches_count"] > 0 else "amber"
    render_metric_card(
        title="Expiring / Expired",
        value=f"{kpis['expiring_soon_count']} / {kpis['expired_batches_count']}",
        subtext=f"{kpis['expiring_soon_count']} within 30d | {kpis['expired_batches_count']} quarantined",
        accent=exp_accent,
        icon="⏳",
    )

with c4:
    low_accent = "red" if kpis["low_stock_count"] > 0 else "blue"
    render_metric_card(
        title="Low Stock Reorders",
        value=f"{kpis['low_stock_count']}",
        subtext=f"{kpis['out_of_stock_count']} completely out of stock",
        accent=low_accent,
        icon="⚠️",
    )

st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. Urgent Attention Banner (If any critical low stock / expiry)
# -------------------------------------------------------------
has_critical = (
    len(urgent_alerts["near_expiry"]) > 0
    or len(urgent_alerts["low_stock"]) > 0
    or kpis["expired_batches_count"] > 0
)

if has_critical:
    with st.expander("🚨 **Urgent Inventory Action Items Require Attention**", expanded=True):
        col_exp, col_low = st.columns(2)

        with col_exp:
            st.markdown("##### ⏳ Near-Expiry Priority Batches (FEFO)")
            if urgent_alerts["near_expiry"]:
                exp_df = pd.DataFrame(
                    [
                        {
                            "Medicine": item["medicine"],
                            "Batch": item["batch_no"],
                            "Expiry Date": item["expiry_date"],
                            "Days Left": f"{item['days_remaining']} days",
                            "Stock": f"{item['quantity']} units",
                        }
                        for item in urgent_alerts["near_expiry"]
                    ]
                )
                st.dataframe(exp_df, use_container_width=True, hide_index=True)
            else:
                st.info("No near-expiry batches detected.")

        with col_low:
            st.markdown("##### ⚠️ Low-Stock Replenishment Queue")
            if urgent_alerts["low_stock"]:
                low_df = pd.DataFrame(
                    [
                        {
                            "Medicine": item["medicine"],
                            "Current Stock": f"{item['current_stock']} units",
                            "Min Safety Threshold": f"{item['min_stock']} units",
                            "Required Deficit": f"+{item['deficit']} units",
                        }
                        for item in urgent_alerts["low_stock"]
                    ]
                )
                st.dataframe(low_df, use_container_width=True, hide_index=True)
            else:
                st.info("All medicine stocks are within safe operational limits.")

st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 3. Interactive Analytics Section
# -------------------------------------------------------------
st.markdown("### :material/analytics: Sales & Inventory Analytics")

col_main_chart, col_side_chart = st.columns([1.6, 1.0])

with col_main_chart:
    st.markdown("##### 📈 Revenue & Order Volume Timeline")
    time_filter = st.segmented_control(
        "Timeline Range",
        options=["7 Days", "14 Days", "30 Days"],
        default="30 Days",
        label_visibility="collapsed",
    )

    days_lookup = {"7 Days": 7, "14 Days": 14, "30 Days": 30}
    selected_days = days_lookup.get(time_filter, 30)

    timeline_data = DashboardService.get_sales_timeline(days=selected_days)
    timeline_df = pd.DataFrame(timeline_data)

    if not timeline_df.empty:
        # Create dual-axis Plotly Chart
        fig_timeline = go.Figure()

        # Revenue Bar Chart
        fig_timeline.add_trace(
            go.Bar(
                x=timeline_df["day_name"],
                y=timeline_df["revenue"],
                name="Revenue (₹)",
                marker_color="#0F766E",
                opacity=0.9,
                hovertemplate="<b>%{x}</b><br>Revenue: ₹%{y:,.2f}<extra></extra>",
            )
        )

        # Invoices / Orders Line Chart
        fig_timeline.add_trace(
            go.Scatter(
                x=timeline_df["day_name"],
                y=timeline_df["orders"],
                name="Orders Completed",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="#D97706", width=2.5),
                marker=dict(size=6, color="#D97706"),
                hovertemplate="<b>%{x}</b><br>Orders: %{y}<extra></extra>",
            )
        )

        fig_timeline.update_layout(
            margin=dict(l=10, r=10, t=20, b=20),
            height=340,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans", color="#1C1917"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                showgrid=False,
                tickangle=-35 if selected_days > 7 else 0,
                tickfont=dict(color="#78716C"),
            ),
            yaxis=dict(
                title=dict(text="Revenue (₹)", font=dict(color="#0F766E", size=12)),
                tickfont=dict(color="#0F766E"),
                showgrid=True,
                gridcolor="#EBE5DC",
            ),
            yaxis2=dict(
                title=dict(text="Orders", font=dict(color="#D97706", size=12)),
                tickfont=dict(color="#D97706"),
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            hovermode="x unified",
        )
        st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("No sales transactions recorded for this period.")

with col_side_chart:
    st.markdown("##### 🏷️ Stock Distribution by Category")
    category_stock = DashboardService.get_stock_by_category()
    if category_stock:
        cat_df = pd.DataFrame(category_stock)
        fig_cat = px.pie(
            cat_df,
            values="total_stock",
            names="category",
            hole=0.45,
            color_discrete_sequence=["#0F766E", "#D97706", "#2563EB", "#059669", "#8B5CF6", "#E11D48"],
        )
        fig_cat.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Stock Units: %{value}<br>Share: %{percent}<extra></extra>",
        )
        fig_cat.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=340,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans", color="#1C1917"),
            showlegend=False,
        )
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No category inventory data available.")

st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 4. Top Selling Products & Recent Transactions
# -------------------------------------------------------------
col_top_meds, col_recent_sales = st.columns([1.1, 1.5])

with col_top_meds:
    st.markdown("##### 🏆 Top Selling Medicines (30 Days)")
    top_meds = DashboardService.get_top_selling_medicines(limit=5, days=30)
    if top_meds:
        top_df = pd.DataFrame(top_meds)
        # Sort ascending for horizontal bar chart display
        top_df_sorted = top_df.sort_values(by="units_sold", ascending=True)

        fig_top = px.bar(
            top_df_sorted,
            x="units_sold",
            y="medicine",
            orientation="h",
            text="units_sold",
            color="units_sold",
            color_continuous_scale=["#99F6E4", "#0D9488"],
            labels={"units_sold": "Units Sold", "medicine": "Medicine"},
        )
        fig_top.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
            xaxis=dict(showgrid=True, gridcolor="#E2E8F0"),
            yaxis=dict(showgrid=False),
        )
        fig_top.update_traces(texttemplate="%{text} units", textposition="outside")
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No sales history to determine top selling medicines.")

with col_recent_sales:
    st.markdown("##### 🧾 Recent Sales Transactions")
    recent_sales = DashboardService.get_recent_sales(limit=5)
    if recent_sales:
        rec_df = pd.DataFrame(
            [
                {
                    "Invoice": s["invoice_no"],
                    "Customer": s["customer"],
                    "Date & Time": s["created_at"],
                    "Items": f"{s['items_count']} items",
                    "Amount": format_currency(s["total_amount"]),
                    "Payment": s["payment_mode"],
                }
                for s in recent_sales
            ]
        )
        st.dataframe(rec_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent sales records.")

# -------------------------------------------------------------
# 5. Quick Operations Navigation Bar
# -------------------------------------------------------------
st.markdown("---")
st.markdown("##### ⚡ Quick Operational Shortcuts")
q1, q2, q3, q4 = st.columns(4)

with q1:
    if st.button("🛒 **New Billing POS**", use_container_width=True, type="primary"):
        st.switch_page("pages/billing.py")

with q2:
    if st.button("📥 **Inward Purchase**", use_container_width=True):
        st.switch_page("pages/purchases.py")

with q3:
    if st.button("⏳ **Expiry Monitor**", use_container_width=True):
        st.switch_page("pages/expiry_monitor.py")

with q4:
    if st.button("⚠️ **Low Stock Reorders**", use_container_width=True):
        st.switch_page("pages/low_stock.py")
