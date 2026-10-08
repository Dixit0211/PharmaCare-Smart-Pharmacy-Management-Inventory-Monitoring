"""System Administration, User Management, Pharmacy Settings, and Database Backup (Admin Only)."""

import streamlit as st
import pandas as pd
from app.utils.session import is_authenticated, is_admin, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.services.auth_service import AuthService
from app.services.setting_service import SettingService
from app.services.backup_service import BackupService
from app.services.notification_service import NotificationService

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

if not is_admin():
    st.error("🚫 Access Denied: System Administration is restricted to Administrator accounts.")
    st.stop()

inject_custom_styles()

try:
    unread_alerts_count = NotificationService.get_unread_count()
except Exception:
    unread_alerts_count = 0

render_sidebar(unread_notifications_count=unread_alerts_count)

current_user = get_current_user()

st.markdown("## :material/admin_panel_settings: System Administration & Governance")
st.caption("Manage staff credentials, pharmacy metadata, regulatory licenses, and database hot backups")

tab_users, tab_settings, tab_backup = st.tabs([
    ":material/group: User Accounts & RBAC",
    ":material/settings: Pharmacy Settings & Licenses",
    ":material/database: Backup & Restore",
])

# -------------------------------------------------------------
# TAB 1: User Accounts & Staff Management
# -------------------------------------------------------------
with tab_users:
    st.markdown("### Registered Pharmacy Staff Accounts")
    
    col_add, _ = st.columns([1.5, 3])
    with col_add:
        if st.button("Add New Staff Account", icon=":material/person_add:", type="primary", use_container_width=True):
            st.session_state["show_add_user_dialog"] = True

    users_list = AuthService.list_users()

    if users_list:
        df_u = pd.DataFrame(
            [
                {
                    "ID": u["id"],
                    "Username": u["username"],
                    "Full Name": u["full_name"],
                    "Email": u["email"],
                    "Role": u["role"].upper(),
                    "Phone": u["phone"] or "-",
                    "Status": "ACTIVE" if u["is_active"] else "DEACTIVATED",
                    "Created": u["created_at"],
                }
                for u in users_list
            ]
        )
        st.dataframe(df_u, use_container_width=True, hide_index=True)

        st.markdown("##### Quick Staff Account Actions")
        c_sel_user, c_toggle, c_reset = st.columns([2, 1.2, 1.2])

        with c_sel_user:
            selected_user_id = st.selectbox(
                "Select Staff Member",
                options=[u["id"] for u in users_list],
                format_func=lambda uid: next(f"#{u['id']} - {u['full_name']} ({u['username']}) - {u['role'].upper()}" for u in users_list if u["id"] == uid),
            )

        target_user = next((u for u in users_list if u["id"] == selected_user_id), None)

        with c_toggle:
            if target_user:
                btn_label = "Deactivate" if target_user["is_active"] else "Activate"
                btn_type = "secondary" if target_user["is_active"] else "primary"
                if st.button(f"{btn_label} User", type=btn_type, use_container_width=True):
                    try:
                        AuthService.toggle_user_status(current_user, target_user["id"])
                        st.toast(f"User status updated for '{target_user['username']}'.", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        with c_reset:
            if target_user:
                if st.button("Reset Password", icon=":material/lock_reset:", use_container_width=True):
                    st.session_state["reset_pwd_target"] = target_user

# -------------------------------------------------------------
# TAB 2: Pharmacy Settings & Metadata
# -------------------------------------------------------------
with tab_settings:
    st.markdown("### Pharmacy Configuration & Statutory Metadata")
    st.caption("Update clinic/hospital header info, drug licenses, GSTIN, and business rules shown on printed invoices")

    current_settings = SettingService.get_all_settings()

    with st.form("pharmacy_settings_form"):
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            st.markdown("##### 🏥 Dispensary Profile")
            pharmacy_name = st.text_input("Pharmacy Name *", value=current_settings.get("pharmacy_name", ""))
            pharmacy_address = st.text_area("Dispensary Address *", value=current_settings.get("pharmacy_address", ""))
            pharmacy_phone = st.text_input("Contact Phone *", value=current_settings.get("pharmacy_phone", ""))
            pharmacy_email = st.text_input("Contact Email *", value=current_settings.get("pharmacy_email", ""))

        with col_s2:
            st.markdown("##### ⚖️ Licensing & Tax Defaults")
            pharmacy_dl_no = st.text_input("Drug License No. (DL) *", value=current_settings.get("pharmacy_dl_no", ""))
            pharmacy_gstin = st.text_input("GSTIN Number *", value=current_settings.get("pharmacy_gstin", ""))
            default_gst_rate = st.text_input("Default GST Rate (%) *", value=current_settings.get("default_gst_rate", "5.0"))
            expiry_warning_days = st.text_input("Expiry Alert Window (Days) *", value=current_settings.get("expiry_warning_days", "30"))
            default_min_stock = st.text_input("Default Low-Stock Threshold *", value=current_settings.get("default_min_stock", "15"))

        st.markdown("##### 📝 Invoice Footer Terms & Conditions")
        invoice_footer_note = st.text_input(
            "Invoice Terms Note",
            value=current_settings.get("invoice_footer_note", "Medicines sold are non-refundable."),
        )

        st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
        save_settings_btn = st.form_submit_button("Save Pharmacy Configuration", type="primary", use_container_width=True)

        if save_settings_btn:
            new_config = {
                "pharmacy_name": pharmacy_name,
                "pharmacy_address": pharmacy_address,
                "pharmacy_phone": pharmacy_phone,
                "pharmacy_email": pharmacy_email,
                "pharmacy_dl_no": pharmacy_dl_no,
                "pharmacy_gstin": pharmacy_gstin,
                "default_gst_rate": default_gst_rate,
                "expiry_warning_days": expiry_warning_days,
                "default_min_stock": default_min_stock,
                "invoice_footer_note": invoice_footer_note,
            }
            try:
                SettingService.update_settings(current_user, new_config)
                st.toast("Pharmacy configuration saved successfully!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))

# -------------------------------------------------------------
# TAB 3: Database Backup & Restore
# -------------------------------------------------------------
with tab_backup:
    st.markdown("### Database Snapshot Backup & Hot Restore")
    st.caption("Perform full offline backups or restore SQLite database snapshots with schema verification")

    db_stats = BackupService.get_database_statistics()

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        render_metric_card("Database Size", f"{db_stats['file_size_kb']} KB", "SQLite binary on disk", accent="teal", icon="💾")
    with b2:
        render_metric_card("Total Sales Invoices", str(db_stats["total_sales"]), "Dispensed records", accent="blue", icon="🧾")
    with b3:
        render_metric_card("Catalog & Batches", f"{db_stats['total_medicines']} / {db_stats['total_batches']}", "Meds / Batches", accent="green", icon="💊")
    with b4:
        render_metric_card("Registered Users", str(db_stats["total_users"]), "Staff accounts", accent="amber", icon="👥")

    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

    col_bk_down, col_bk_up = st.columns(2)

    with col_bk_down:
        with st.container(border=True):
            st.markdown("#### 📥 Create Hot Backup Snapshot")
            st.write(
                "Export an instant, consistent binary snapshot of the active SQLite database without locking live counter operations."
            )
            st.caption(f"Target file: `{db_stats['file_path']}`")
            st.caption(f"Last modified: `{db_stats['last_modified']}`")

            if st.button("Generate Downloadable Backup", icon=":material/download:", type="primary", use_container_width=True):
                try:
                    bk_bytes, bk_filename = BackupService.create_database_backup(current_user)
                    st.download_button(
                        label=f"Click to Save {bk_filename}",
                        data=bk_bytes,
                        file_name=bk_filename,
                        mime="application/x-sqlite3",
                        icon=":material/save:",
                        type="primary",
                        use_container_width=True,
                    )
                    st.toast("Backup snapshot generated successfully!", icon="✅")
                except Exception as e:
                    st.error(f"Backup failed: {str(e)}")

    with col_bk_up:
        with st.container(border=True):
            st.markdown("#### 📤 Restore Database from Snapshot")
            st.write(
                "Upload a verified `.db` backup file. A pre-restore safety copy of the current database will automatically be saved."
            )
            st.warning("⚠️ **Caution**: Restoring will replace current records with the uploaded snapshot.")

            uploaded_db = st.file_uploader("Select SQLite Backup (.db)", type=["db", "sqlite", "sqlite3"])
            confirm_restore = st.checkbox("I understand this will overwrite current live pharmacy data.")

            if st.button("Execute Restore", icon=":material/restore:", type="secondary", disabled=not (uploaded_db and confirm_restore), use_container_width=True):
                try:
                    raw_bytes = uploaded_db.read()
                    BackupService.restore_database_backup(current_user, raw_bytes)
                    st.success("Database restored successfully! Reloading system...")
                    st.toast("Database restored successfully!", icon="🎉")
                    st.rerun()
                except Exception as e:
                    st.error(f"Restore failed: {str(e)}")


# -------------------------------------------------------------
# Modals & Dialogs
# -------------------------------------------------------------
@st.dialog("Create Staff User Account")
def add_user_dialog(curr_user):
    """Modal dialog for admin to add a new pharmacist or admin."""
    with st.form("add_user_form"):
        st.write("Enter staff user details:")
        username = st.text_input("Username *", placeholder="e.g. jdoe")
        full_name = st.text_input("Full Name *", placeholder="e.g. John Doe")
        email = st.text_input("Email Address *", placeholder="e.g. jdoe@pharmacare.local")
        password = st.text_input("Temporary Password *", type="password")
        role = st.selectbox("Role *", options=["pharmacist", "admin"], index=0)
        phone = st.text_input("Phone Number", placeholder="e.g. +91 98765 43210")

        submit = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        if submit:
            try:
                AuthService.create_user(
                    current_user=curr_user,
                    username=username,
                    email=email,
                    password=password,
                    full_name=full_name,
                    role=role,
                    phone=phone,
                )
                st.toast(f"User '{username}' created successfully!", icon="✅")
                st.session_state["show_add_user_dialog"] = False
                st.rerun()
            except Exception as e:
                st.error(str(e))


@st.dialog("Admin Password Reset")
def reset_pwd_dialog(target_user):
    """Modal dialog for admin to force reset a staff password."""
    st.write(f"Reset password for **{target_user['full_name']}** (`{target_user['username']}`):")
    with st.form("reset_pwd_form"):
        new_pwd = st.text_input("New Temporary Password *", type="password")
        confirm_pwd = st.text_input("Confirm New Password *", type="password")
        submit = st.form_submit_button("Set New Password", type="primary", use_container_width=True)

        if submit:
            if not new_pwd or not confirm_pwd:
                st.error("Please enter and confirm the new password.")
            elif new_pwd != confirm_pwd:
                st.error("Passwords do not match.")
            elif len(new_pwd) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    AuthService.admin_reset_password(current_user, target_user["id"], new_pwd)
                    st.toast(f"Password reset for '{target_user['username']}'!", icon="✅")
                    st.session_state.pop("reset_pwd_target", None)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))



if st.session_state.get("show_add_user_dialog", False):
    add_user_dialog(current_user)

if st.session_state.get("reset_pwd_target"):
    reset_pwd_dialog(st.session_state["reset_pwd_target"])
