"""Audit Logs and Regulatory Compliance Trail page module (Admin Only)."""

import streamlit as st
import pandas as pd
from app.utils.session import is_authenticated, is_admin
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.empty_state import render_empty_state
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.report_service import ReportService

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

if not is_admin():
    st.error("🚫 Access Denied: Audit logs and compliance trails are restricted to Administrator accounts.")
    st.stop()

inject_custom_styles()

try:
    unread_alerts_count = NotificationService.get_unread_count()
except Exception:
    unread_alerts_count = 0

render_sidebar(unread_notifications_count=unread_alerts_count)

st.markdown("## :material/security: Compliance & Audit Logs")
st.caption("Immutable tamper-evident record of all system operations, authentications, and stock adjustments")

# -------------------------------------------------------------
# 1. Filters & Search Bar
# -------------------------------------------------------------
col_mod, col_act, col_user, col_search = st.columns([1.2, 1.2, 1.2, 1.6])

with col_mod:
    module_filter = st.selectbox(
        "Module",
        options=["All", "AUTH", "BILLING", "PURCHASES", "INVENTORY", "USERS", "SETTINGS", "DATABASE"],
        index=0,
    )

with col_act:
    action_filter = st.selectbox(
        "Action",
        options=["All", "LOGIN", "CREATE", "UPDATE", "DELETE", "DISPOSE", "BACKUP", "RESTORE", "CHANGE_PASSWORD"],
        index=0,
    )

with col_user:
    user_search = st.text_input("Username", placeholder="e.g. admin")

with col_search:
    keyword = st.text_input("Search Description", placeholder="e.g. invoice, batch, Paracetamol...")

# -------------------------------------------------------------
# 2. Fetch and Filter Audit Records
# -------------------------------------------------------------
all_logs = AuditService.get_audit_logs(limit=250)

filtered_logs = []
for log in all_logs:
    if module_filter != "All" and log.get("module") != module_filter:
        continue
    if action_filter != "All" and log.get("action") != action_filter:
        continue
    if user_search and user_search.lower() not in (log.get("username") or "").lower():
        continue
    if keyword and keyword.lower() not in (log.get("description") or "").lower():
        continue
    filtered_logs.append(log)

# -------------------------------------------------------------
# 3. Action Bar & Table Display
# -------------------------------------------------------------
col_count, col_dl = st.columns([3, 1.2])
with col_count:
    st.caption(f"Showing **{len(filtered_logs)}** audit events (out of {len(all_logs)} cached)")

with col_dl:
    if filtered_logs:
        csv_logs = ReportService.export_to_csv(
            filtered_logs,
            fieldnames=["timestamp", "username", "module", "action", "description", "ip_address"],
        )
        st.download_button(
            label="Export Audit Trail (CSV)",
            data=csv_logs,
            file_name="pharmacare_audit_trail.csv",
            mime="text/csv",
            icon=":material/download:",
            use_container_width=True,
        )

if not filtered_logs:
    render_empty_state("No Audit Events Found", "No system actions match the selected filter criteria.", icon="🔍")
else:
    df_logs = pd.DataFrame(filtered_logs)
    df_logs = df_logs[["timestamp", "username", "module", "action", "description", "ip_address"]]
    df_logs.columns = ["Timestamp", "User", "Module", "Action", "Description", "IP Address"]

    st.dataframe(
        df_logs,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Timestamp": st.column_config.TextColumn(width="medium"),
            "User": st.column_config.TextColumn(width="small"),
            "Module": st.column_config.TextColumn(width="small"),
            "Action": st.column_config.TextColumn(width="small"),
            "Description": st.column_config.TextColumn(width="large"),
            "IP Address": st.column_config.TextColumn(width="small"),
        },
    )
