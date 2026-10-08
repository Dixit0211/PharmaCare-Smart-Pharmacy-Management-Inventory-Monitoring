"""Low stock monitoring and automated replenishment reorder suggestions page."""

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
from app.services.inventory_service import InventoryService
from app.services.medicine_service import MedicineService
from app.core.exceptions import AppException

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/warning: Low Stock & Reorder Monitor")
st.caption("Identify items below safety thresholds, calculate deficit replenishments, and generate procurement purchase orders")

# Fetch dynamic low stock overview
low_stock_data = InventoryService.get_low_stock_overview()

# Summary KPI Cards
k1, k2, k3, k4 = st.columns(4)
with k1:
    render_metric_card(
        "Out of Stock",
        str(low_stock_data["out_of_stock_count"]),
        "Immediate stockout alert",
        accent="red" if low_stock_data["out_of_stock_count"] > 0 else "teal",
        icon="🚫",
    )
with k2:
    render_metric_card(
        "Below Safety Level",
        str(low_stock_data["below_threshold_count"]),
        "Stock ≤ Minimum threshold",
        accent="amber" if low_stock_data["below_threshold_count"] > 0 else "teal",
        icon="⚠️",
    )
with k3:
    render_metric_card(
        "Suggested Reorder",
        f"{low_stock_data['total_suggested_reorder_units']:,} units",
        "Recommended replenishment",
        accent="blue",
        icon="📦",
    )
with k4:
    render_metric_card(
        "Est. Reorder Cost",
        f"₹{low_stock_data['total_estimated_reorder_cost']:,.2f}",
        "Approx. wholesale procurement cost",
        accent="green",
        icon="💰",
    )

st.markdown("---")

tab_reorder_list, tab_thresholds = st.tabs([
    f":material/shopping_cart_checkout: Reorder Recommendations ({low_stock_data['total_low_stock_items']})",
    ":material/tune: Adjust Reorder Thresholds",
])

# ==============================================================================
# TAB 1: REORDER RECOMMENDATIONS & CSV EXPORT
# ==============================================================================
with tab_reorder_list:
    c_hdr1, c_hdr2 = st.columns([3, 1])
    with c_hdr1:
        st.markdown("### 📋 Replenishment Queue")
        st.caption("Suggested reorder quantities are calculated to bring stock levels back to optimal 2× safety reserves.")
    with c_hdr2:
        if low_stock_data["total_low_stock_items"] > 0:
            csv_data = InventoryService.export_low_stock_csv()
            st.download_button(
                label="Download Reorder Sheet (CSV)",
                data=csv_data,
                file_name=f"pharmacare_reorder_list_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                icon=":material/download:",
                type="primary",
                use_container_width=True,
            )

    items = low_stock_data["items"]
    if not items:
        st.success("🎉 All medicines are currently well above safety stock thresholds! No reorders required.")
    else:
        table_rows = []
        for it in items:
            status_tag = "Out of Stock" if it["current_stock"] == 0 else "Low Stock"
            table_rows.append({
                "Medicine Name": it["medicine_name"],
                "Category": it["category"],
                "Dosage Form": it["dosage_form"],
                "Current Stock": f"{it['current_stock']} units",
                "Min Stock Threshold": f"{it['min_stock']} units",
                "Deficit": f"{it['deficit']} units",
                "Suggested Reorder": f"{it['suggested_reorder_qty']} units",
                "Est. Unit Cost": f"₹{it['est_unit_cost']:.2f}",
                "Est. Total Cost": f"₹{it['est_total_cost']:.2f}",
                "Urgency": status_tag,
            })

        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 2: ADJUST REORDER THRESHOLDS (MIN_STOCK)
# ==============================================================================
with tab_thresholds:
    st.markdown("### ⚙️ Safety Stock & Minimum Threshold Configuration")
    st.caption("Customize the minimum stock buffer for individual medicines based on seasonal demand or consumption rates.")

    all_meds = MedicineService.list_medicines()
    if not all_meds:
        render_empty_state("No Medicines", "No products available in catalog.")
    else:
        med_choices = {f"{m['name']} ({m['strength']}) - Current Min: {m['min_stock']} | Stock: {m['total_stock']}": m for m in all_meds}
        sel_label = st.selectbox("Select medicine to update safety threshold:", options=list(med_choices.keys()))
        selected_med = med_choices[sel_label]

        with st.form("update_min_stock_form"):
            st.write(f"Adjust safety buffer for **{selected_med['name']} ({selected_med['strength']})**:")
            new_min = st.number_input(
                "New Minimum Stock Threshold (Units) *",
                min_value=0,
                max_value=1000,
                value=int(selected_med["min_stock"]),
                step=5,
                help="When total non-expired stock falls to or below this count, a reorder alert is triggered.",
            )

            submit = st.form_submit_button("Update Threshold", type="primary", use_container_width=True)
            if submit:
                try:
                    InventoryService.update_medicine_min_stock(
                        current_user=current_user,
                        medicine_id=selected_med["id"],
                        new_min_stock=int(new_min),
                    )
                    st.toast(f"Minimum stock for '{selected_med['name']}' updated to {new_min} units!", icon="✅")
                    st.rerun()
                except AppException as e:
                    st.error(e.message)
