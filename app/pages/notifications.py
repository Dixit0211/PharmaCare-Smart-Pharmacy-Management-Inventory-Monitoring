"""System alerts, inventory triggers, and notification center page."""

import streamlit as st
from app.utils.session import is_authenticated, is_admin, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.status_badge import get_status_badge_html
from app.components.empty_state import render_empty_state
from app.services.notification_service import NotificationService

if not is_authenticated():
    st.warning("Please log in to access system notifications.")
    st.stop()

inject_custom_styles()

# Auto-sync inventory alerts
try:
    NotificationService.sync_inventory_alerts()
    unread_count = NotificationService.get_unread_count()
except Exception:
    unread_count = 0

render_sidebar(unread_notifications_count=unread_count)

user = get_current_user()

st.markdown("## :material/notifications: Notification & Alert Center")
st.caption("Real-time clinical triggers: expiry warnings, low-stock safety limits, and system notices")

# -------------------------------------------------------------
# 1. Action Bar & Filter Bar
# -------------------------------------------------------------
col_filters, col_actions = st.columns([1.5, 1.2])

with col_filters:
    filter_tab = st.segmented_control(
        "Filter Alerts",
        options=["All Alerts", "Unread Only", "Critical / Warnings", "Resolved"],
        default="Unread Only" if unread_count > 0 else "All Alerts",
        label_visibility="collapsed",
    )

with col_actions:
    a1, a2, a3 = st.columns([1, 1, 1.2])
    with a1:
        if st.button("Mark All Read", icon=":material/done_all:", use_container_width=True, help="Mark all alerts as read"):
            updated = NotificationService.mark_all_as_read()
            st.toast(f"Marked {updated} alerts as read.", icon="✅")
            st.rerun()

    with a2:
        if st.button("Clear Read", icon=":material/delete_sweep:", use_container_width=True, help="Delete all resolved notifications"):
            cleared = NotificationService.clear_read_notifications()
            st.toast(f"Cleared {cleared} read notifications.", icon="🗑️")
            st.rerun()

    with a3:
        if is_admin():
            if st.button("Broadcast Notice", icon=":material/campaign:", type="primary", use_container_width=True):
                st.session_state["show_broadcast_dialog"] = True

# -------------------------------------------------------------
# 2. Fetch Notifications according to selected filter
# -------------------------------------------------------------
if filter_tab == "Unread Only":
    notifications = NotificationService.get_notifications(is_read=False, limit=60)
elif filter_tab == "Resolved":
    notifications = NotificationService.get_notifications(is_read=True, limit=60)
elif filter_tab == "Critical / Warnings":
    all_notifs = NotificationService.get_notifications(limit=100)
    notifications = [n for n in all_notifs if n["severity"] in ["critical", "warning"]]
else:
    notifications = NotificationService.get_notifications(limit=60)

# -------------------------------------------------------------
# 3. Notification List Display
# -------------------------------------------------------------
if not notifications:
    render_empty_state(
        title="No Notifications Found",
        message="Your notification inbox is clean. No active alerts match the selected filter.",
        icon="🔔",
    )
else:
    st.caption(f"Showing **{len(notifications)}** alerts")

    severity_colors = {
        "critical": {"border": "#EF4444", "badge": "badge-critical", "icon": "🔴"},
        "warning": {"border": "#F59E0B", "badge": "badge-warning", "icon": "🟠"},
        "info": {"border": "#3B82F6", "badge": "badge-info", "icon": "🔵"},
        "system": {"border": "#64748B", "badge": "badge-neutral", "icon": "ℹ️"},
    }

    for n in notifications:
        s_info = severity_colors.get(n["severity"], severity_colors["info"])
        border_color = s_info["border"] if not n["is_read"] else "#E2E8F0"
        bg_color = "#FFFFFF" if not n["is_read"] else "#F8FAFC"
        opacity = "1.0" if not n["is_read"] else "0.75"

        with st.container():
            col_content, col_btns = st.columns([4, 1.2])

            with col_content:
                st.markdown(
                    f"""
                    <div style="
                        background: {bg_color};
                        border: 1px solid {border_color};
                        border-left: 5px solid {s_info['border']};
                        border-radius: 8px;
                        padding: 0.85rem 1.1rem;
                        margin-bottom: 0.5rem;
                        opacity: {opacity};
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <span>{s_info['icon']}</span>
                                <strong style="color: #0F172A; font-size: 0.95rem;">{n['title']}</strong>
                                <span class="status-badge {s_info['badge']}">{n['severity'].upper()}</span>
                                {"<span class='status-badge badge-safe'>READ</span>" if n['is_read'] else "<span class='status-badge badge-critical'>NEW</span>"}
                            </div>
                            <span style="color: #64748B; font-size: 0.75rem;">{n['created_at']}</span>
                        </div>
                        <div style="color: #334155; font-size: 0.85rem; line-height: 1.4;">
                            {n['message']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col_btns:
                b1, b2 = st.columns(2)
                with b1:
                    if not n["is_read"]:
                        if st.button("Read", key=f"read_{n['id']}", icon=":material/check:", use_container_width=True, help="Mark as read"):
                            NotificationService.mark_as_read(n["id"])
                            st.rerun()
                    else:
                        st.caption("Resolved")

                with b2:
                    if st.button("Delete", key=f"del_{n['id']}", icon=":material/delete:", use_container_width=True, help="Delete notification"):
                        NotificationService.delete_notification(n["id"])
                        st.rerun()

            st.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)


# -------------------------------------------------------------
# 4. Broadcast Notification Modal Dialog (Admin Only)
# -------------------------------------------------------------
@st.dialog("Broadcast System Notice")
def broadcast_dialog():
    """Modal dialog for administrators to broadcast system-wide notices."""
    st.write("Post an announcement or high-priority notice to all pharmacy staff:")
    with st.form("broadcast_notice_form"):
        title = st.text_input("Notice Title *", placeholder="e.g. Scheduled System Maintenance / Stock Audit")
        message = st.text_area("Notice Details *", placeholder="Provide relevant details or operational instructions for staff...")
        severity = st.selectbox("Severity Level", options=["info", "warning", "critical"], format_func=lambda s: s.capitalize())

        submit = st.form_submit_button("Broadcast to System", type="primary", use_container_width=True)
        if submit:
            if not title or not message:
                st.error("Please fill in both title and notice details.")
            else:
                try:
                    NotificationService.create_notification(
                        title=title,
                        message=message,
                        severity=severity,
                        notif_type="system",
                    )
                    st.toast("Notice broadcasted successfully!", icon="📢")
                    st.session_state["show_broadcast_dialog"] = False
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


if st.session_state.get("show_broadcast_dialog", False):
    broadcast_dialog()
