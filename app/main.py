"""Main entry point for PharmaCare Streamlit application."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import AuthenticationError, ValidationError, AppException
from app.core.logging import get_logger
from app.services.auth_service import AuthService
from app.utils.session import (
    init_session,
    is_authenticated,
    is_admin,
    login_user,
    check_session_timeout,
    get_current_user,
)
from app.components.styles import inject_custom_styles

logger = get_logger(__name__)

# Configure Streamlit page settings
st.set_page_config(
    page_title="PharmaCare - Pharmacy Management",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_login_page() -> None:
    """Render clinical authentication portal."""
    inject_custom_styles()

    # Center card container
    _, col_center, _ = st.columns([1, 1.8, 1])

    with col_center:
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

        # Hospital Branding Card
        st.markdown(
            f"""
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <div style="display: inline-flex; align-items: center; justify-content: center; width: 76px; height: 76px; background: linear-gradient(135deg, #0F766E 0%, #115E59 100%); border-radius: 20px; margin-bottom: 0.85rem; box-shadow: 0 8px 24px rgba(15, 118, 110, 0.25);">
                    <span style="font-size: 2.5rem;">💊</span>
                </div>
                <h1 style="color: #1C1917; margin: 0; font-size: 2rem; font-weight: 800; letter-spacing: -0.03em;">PharmaCare</h1>
                <p style="color: #78716C; font-size: 0.98rem; margin-top: 0.35rem; font-weight: 500;">Smart Pharmacy Management & Inventory Monitoring</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown("#### Staff Portal Login")
            st.caption("Enter your registered credentials to access the pharmacy system.")

            with st.form("login_form", clear_on_submit=False):
                identifier = st.text_input(
                    "Email or Username",
                    placeholder="e.g. admin@pharmacare.local",
                    help="Enter your registered email address or username",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="••••••••",
                    help="Enter your secure password",
                )

                submit_btn = st.form_submit_button(
                    "Sign In to PharmaCare",
                    type="primary",
                    use_container_width=True,
                )

                if submit_btn:
                    if not identifier or not password:
                        st.error("Please provide both email/username and password.")
                    else:
                        try:
                            user_data = AuthService.authenticate(
                                identifier=identifier,
                                password=password,
                            )
                            login_user(user_data)
                            st.toast(f"Welcome, {user_data['full_name']}!", icon="👋")
                            st.rerun()
                        except AuthenticationError as e:
                            st.error(str(e))
                        except AppException as e:
                            st.error(f"Login failed: {e.message}")
                        except Exception as e:
                            logger.error(f"Unexpected error during login: {e}", exc_info=True)
                            st.error("A system error occurred. Please try again later.")

            st.markdown("---")
            st.caption("🧪 **Demo Viva Quick Logins:**")
            col_admin, col_pharma = st.columns(2)
            with col_admin:
                if st.button("👑 Admin Demo", use_container_width=True, help="Auto-login as Dr. Alok Verma (Admin)"):
                    try:
                        u = AuthService.authenticate("admin@pharmacare.local", "Admin@123")
                        login_user(u)
                        st.rerun()
                    except Exception as err:
                        st.error(str(err))
            with col_pharma:
                if st.button("💊 Pharmacist Demo", use_container_width=True, help="Auto-login as Neha Deshmukh (Pharmacist)"):
                    try:
                        u = AuthService.authenticate("pharmacist@pharmacare.local", "Pharma@123")
                        login_user(u)
                        st.rerun()
                    except Exception as err:
                        st.error(str(err))


def main() -> None:
    """Initialize system, enforce authentication guards, and build page navigation."""
    # Ensure database tables exist
    init_db()
    init_session()

    # Verify session timeout
    if check_session_timeout():
        st.warning("Your session expired due to inactivity. Please log in again.")
        render_login_page()
        return

    # Check authentication state
    if not is_authenticated():
        render_login_page()
        return

    # User is authenticated: construct role-aware navigation
    admin_mode = is_admin()

    # Core Navigation Structure
    pages_structure = {
        "Overview": [
            st.Page("pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        ],
        "Inventory & Batches": [
            st.Page("pages/medicines.py", title="Medicines Catalog", icon=":material/medication:"),
            st.Page("pages/expiry_monitor.py", title="Expiry Monitor", icon=":material/event_busy:"),
            st.Page("pages/low_stock.py", title="Low Stock Alerts", icon=":material/warning:"),
        ],
        "Point of Sale": [
            st.Page("pages/billing.py", title="Billing Counter", icon=":material/point_of_sale:"),
            st.Page("pages/sales_history.py", title="Sales Invoices", icon=":material/receipt_long:"),
            st.Page("pages/prescriptions.py", title="Prescriptions", icon=":material/prescriptions:"),
        ],
        "Procurement": [
            st.Page("pages/purchases.py", title="Stock Purchases", icon=":material/inventory_2:"),
            st.Page("pages/suppliers.py", title="Suppliers", icon=":material/local_shipping:"),
        ],
        "Directory & CRM": [
            st.Page("pages/customers.py", title="Customers & Patients", icon=":material/group:"),
        ],
        "Analytics & Alerts": [
            st.Page("pages/reports.py", title="Reports & Export", icon=":material/analytics:"),
            st.Page("pages/notifications.py", title="Notifications", icon=":material/notifications:"),
        ],
    }

    # Restrict Admin modules only to administrators
    if admin_mode:
        pages_structure["Administration"] = [
            st.Page("pages/audit_logs.py", title="Audit Logs", icon=":material/security:"),
            st.Page("pages/admin.py", title="System Administration", icon=":material/admin_panel_settings:"),
        ]

    nav = st.navigation(pages_structure)
    nav.run()


if __name__ == "__main__":
    main()
