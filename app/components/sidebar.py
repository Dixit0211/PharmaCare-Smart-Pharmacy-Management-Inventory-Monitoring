"""Sidebar navigation header, user profile card, and session controls."""

from pathlib import Path
import streamlit as st
from app.core.config import settings
from app.utils.session import get_current_user, logout_user, is_admin
from app.components.status_badge import get_status_badge_html
from app.services.auth_service import AuthService


def render_sidebar(unread_notifications_count: int = 0) -> None:
    """Render branded hospital sidebar with user profile and session controls."""
    user = get_current_user()
    if not user:
        return

    with st.sidebar:
        # Branding Header
        logo_path = Path(settings.LOGO_PATH)
        if logo_path.exists():
            st.image(str(logo_path), width=48)

        st.markdown(
            """
            <div style="margin-bottom: 1.25rem; padding: 0.25rem 0;">
                <h3 style="color: #1C1917; margin: 0; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.02em;">💊 PharmaCare</h3>
                <span style="color: #78716C; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;">Smart Pharmacy Management</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # User Profile Chip
        role_label = "Administrator" if user.get("role") == "admin" else "Pharmacist"
        role_badge = get_status_badge_html(user.get("role", "pharmacist"), role_label)

        profile_html = f"""
        <div class="user-profile-chip">
            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.4rem;">
                <div style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #0F766E 0%, #115E59 100%); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.9rem; box-shadow: 0 2px 6px rgba(15, 118, 110, 0.25);">
                    {user.get("username", "U")[:1].upper()}
                </div>
                <div>
                    <div class="user-profile-name">{user.get("full_name", user.get("username"))}</div>
                    <div class="user-profile-email">{user.get("email", "")}</div>
                </div>
            </div>
            <div style="margin-top: 0.5rem;">
                {role_badge}
            </div>
        </div>
        """
        st.markdown(profile_html, unsafe_allow_html=True)

        if unread_notifications_count > 0:
            st.caption(f":material/notifications_active: **{unread_notifications_count}** unread alerts")

        st.divider()

        # Session Controls
        col_pwd, col_logout = st.columns(2)
        with col_pwd:
            if st.button("Password", icon=":material/key:", use_container_width=True, help="Change your login password"):
                change_password_dialog(user["id"])

        with col_logout:
            if st.button("Logout", icon=":material/logout:", use_container_width=True, type="secondary"):
                logout_user()
                st.rerun()


@st.dialog("Change Password")
def change_password_dialog(user_id: int):
    """Modal dialog for updating user password."""
    st.write("Update your account credentials:")
    with st.form("change_pwd_form"):
        old_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password (min 6 chars)", type="password")
        confirm_pwd = st.text_input("Confirm New Password", type="password")
        submit = st.form_submit_button("Update Password", type="primary", use_container_width=True)

        if submit:
            if not old_pwd or not new_pwd or not confirm_pwd:
                st.error("Please fill in all password fields.")
            elif new_pwd != confirm_pwd:
                st.error("New passwords do not match.")
            elif len(new_pwd) < 6:
                st.error("New password must be at least 6 characters.")
            else:
                try:
                    AuthService.change_password(user_id, old_pwd, new_pwd)
                    st.toast("Password updated successfully!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
