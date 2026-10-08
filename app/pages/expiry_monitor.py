"""Expiry monitor and batch quarantine management page."""

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
from app.core.exceptions import AppException

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/event_busy: Expiry Date & Quarantine Monitor")
st.caption("Real-time drug expiration tracking, statutory batch quarantine, FEFO dispensing prioritization, and disposal auditing")

# Configurable Warning Window
col_title, col_window = st.columns([3, 1])
with col_window:
    default_days = InventoryService.get_expiry_warning_days()
    window_days = st.selectbox(
        "Expiry Warning Window",
        options=[15, 30, 45, 60, 90],
        index=[15, 30, 45, 60, 90].index(default_days) if default_days in [15, 30, 45, 60, 90] else 1,
        help="Medicines expiring within this number of days are highlighted for priority dispensing.",
    )

# Fetch dynamic expiry overview
expiry_data = InventoryService.get_expiry_overview(warning_days=window_days)

# KPI Metric Cards
k1, k2, k3, k4 = st.columns(4)
with k1:
    render_metric_card(
        "Expired Batches",
        str(expiry_data["expired_batches_count"]),
        f"{expiry_data['expired_units_total']} units quarantined",
        accent="red" if expiry_data["expired_batches_count"] > 0 else "teal",
        icon="⚠️",
    )
with k2:
    render_metric_card(
        "Total Expired Loss",
        f"₹{expiry_data['expired_loss_value']:,.2f}",
        "Cost value of expired stock",
        accent="red" if expiry_data["expired_loss_value"] > 0 else "teal",
        icon="💸",
    )
with k3:
    render_metric_card(
        f"Expiring in ≤{window_days}d",
        str(expiry_data["expiring_soon_batches_count"]),
        f"{expiry_data['expiring_soon_units_total']} units to sell (FEFO)",
        accent="amber" if expiry_data["expiring_soon_batches_count"] > 0 else "teal",
        icon="⏳",
    )
with k4:
    render_metric_card(
        "Near-Expiry Value",
        f"₹{expiry_data['expiring_soon_value']:,.2f}",
        "Value requiring rapid turnover",
        accent="amber" if expiry_data["expiring_soon_value"] > 0 else "teal",
        icon="📊",
    )

st.markdown("---")

tab_expired, tab_near, tab_all = st.tabs([
    f":material/cancel: Expired Batches ({expiry_data['expired_batches_count']})",
    f":material/schedule: Expiring Soon ({expiry_data['expiring_soon_batches_count']})",
    f":material/list_alt: All Batches ({expiry_data['total_batches_count']})",
])

# ==============================================================================
# TAB 1: EXPIRED BATCHES & QUARANTINE LOG
# ==============================================================================
with tab_expired:
    st.markdown("### ⚠️ Quarantined & Expired Physical Batches")
    st.caption("Expired batches are automatically blocked from Point of Sale billing. Record formal disposal for regulatory records.")

    expired_list = expiry_data["expired_batches"]
    if not expired_list:
        st.success("🎉 No expired batches currently in stock. All batches are safe and within valid expiry dates.")
    else:
        # Table of expired batches
        exp_table = []
        for b in expired_list:
            exp_table.append({
                "Batch ID": b["batch_id"],
                "Medicine Name": b["medicine_name"],
                "Category": b["category"],
                "Batch Number": b["batch_no"],
                "Expiry Date": b["expiry_date"],
                "Days Expired": f"{abs(b['days_remaining'])} days ago",
                "Quarantined Quantity": f"{b['quantity']} units",
                "Purchase Price": f"₹{b['purchase_price']:.2f}",
                "Loss Value": f"₹{b['total_value']:.2f}",
            })

        st.dataframe(pd.DataFrame(exp_table), use_container_width=True, hide_index=True)

        st.markdown("#### Dispose / Quarantine Action")
        exp_choices = {
            f"Batch {b['batch_no']} ({b['medicine_name']}) - Qty: {b['quantity']} (Loss: ₹{b['total_value']:.2f})": b
            for b in expired_list if b["quantity"] > 0
        }

        if exp_choices:
            sel_exp_label = st.selectbox("Select expired batch to record disposal:", options=list(exp_choices.keys()))
            sel_exp_batch = exp_choices[sel_exp_label]

            col_disp, _ = st.columns([2, 3])
            with col_disp:
                if st.button("Quarantine & Discard Batch", icon=":material/delete_forever:", type="primary"):
                    discard_batch_dialog(current_user, sel_exp_batch)
        else:
            st.info("All expired batches have been zeroed out / formally discarded.")


# ==============================================================================
# TAB 2: EXPIRING SOON (FEFO PRIORITIZATION)
# ==============================================================================
with tab_near:
    st.markdown(f"### ⏳ Batches Expiring in ≤ {window_days} Days")
    st.caption("Prioritize these batches for dispensing at the billing counter (First-Expiry-First-Out rule).")

    near_list = expiry_data["expiring_soon_batches"]
    if not near_list:
        st.info(f"No batches expiring within the next {window_days} days.")
    else:
        near_table = []
        for b in near_list:
            near_table.append({
                "Batch ID": b["batch_id"],
                "Medicine Name": b["medicine_name"],
                "Category": b["category"],
                "Batch Number": b["batch_no"],
                "Expiry Date": b["expiry_date"],
                "Days Remaining": f"⏳ {b['days_remaining']} days",
                "Available Qty": f"{b['quantity']} units",
                "Purchase Cost": f"₹{b['purchase_price']:.2f}",
                "Stock Value": f"₹{b['total_value']:.2f}",
                "Priority": b["urgency"],
            })

        st.dataframe(pd.DataFrame(near_table), use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 3: COMPLETE EXPIRED & SAFE AUDIT WITH CSV EXPORT
# ==============================================================================
with tab_all:
    st.markdown("### 📋 Complete Expiry Audit Registry")
    st.caption("Master list of physical batches across all therapeutic categories and lifecycle stages.")

    c_exp_btn, _ = st.columns([2, 4])
    with c_exp_btn:
        csv_data = InventoryService.export_expiry_report_csv(warning_days=window_days)
        st.download_button(
            label="Download Expiry Report (CSV)",
            data=csv_data,
            file_name=f"pharmacare_expiry_audit_{date.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            icon=":material/download:",
            type="primary",
            use_container_width=True,
        )

    all_table = []
    for b in expiry_data["all_batches"]:
        all_table.append({
            "Medicine": b["medicine_name"],
            "Batch No": b["batch_no"],
            "Category": b["category"],
            "Expiry Date": b["expiry_date"],
            "Days Left": f"{b['days_remaining']}d" if b['days_remaining'] >= 0 else f"EXPIRED ({abs(b['days_remaining'])}d ago)",
            "Quantity": f"{b['quantity']} units",
            "Stock Value": f"₹{b['total_value']:.2f}",
            "Status": b["status"].replace("_", " ").title(),
        })

    st.dataframe(pd.DataFrame(all_table), use_container_width=True, hide_index=True)


# ==============================================================================
# MODAL DIALOGS
# ==============================================================================

@st.dialog("Record Batch Disposal / Quarantine")
def discard_batch_dialog(curr_user, batch_obj):
    """Modal to record formal destruction and zeroing of an expired batch."""
    st.write(f"Dispose Expired Stock for **{batch_obj['medicine_name']}**")
    st.write(f"Batch: **{batch_obj['batch_no']}** | Quantity: **{batch_obj['quantity']} units**")
    st.write(f"Estimated Loss: **₹{batch_obj['total_value']:.2f}**")

    with st.form("discard_batch_form"):
        reason = st.selectbox(
            "Disposal Protocol Reason *",
            options=[
                "Standard statutory quarantine and incinerate",
                "Manufacturer return / credit note claim",
                "Quarantined in hazardous waste storage",
                "State drug inspector witnessed disposal",
            ],
        )
        inspector_notes = st.text_input("Authorization / Officer Notes", placeholder="e.g. Cleared under disposal batch #D-2026-04")

        submit = st.form_submit_button("Confirm Discard & Zero Stock", type="primary", use_container_width=True)
        if submit:
            try:
                full_reason = f"{reason} - {inspector_notes}" if inspector_notes else reason
                res = InventoryService.quarantine_and_discard_batch(
                    current_user=curr_user,
                    batch_id=batch_obj["batch_id"],
                    reason=full_reason,
                )
                st.toast(f"Batch '{batch_obj['batch_no']}' disposed ({res['discarded_quantity']} units zeroed).", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)
