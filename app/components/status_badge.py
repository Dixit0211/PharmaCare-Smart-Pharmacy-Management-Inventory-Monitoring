"""Reusable status badges for medicines, inventory, and user roles."""

import streamlit as st


def get_status_badge_html(status: str, custom_label: str = None) -> str:
    """Generate HTML pill badge based on status value."""
    status_lower = (status or "").lower().strip()
    label = custom_label or status

    css_class = "badge-neutral"
    icon = "●"

    if status_lower in ["safe", "active", "received", "in_stock", "paid", "normal"]:
        css_class = "badge-safe"
        icon = "✓"
    elif status_lower in ["expiring_soon", "warning", "pending", "near_expiry"]:
        css_class = "badge-warning"
        icon = "⚠"
    elif status_lower in ["expired", "critical", "low_stock", "out_of_stock", "cancelled", "inactive"]:
        css_class = "badge-critical"
        icon = "✕"
    elif status_lower in ["info", "admin", "pharmacist", "doctor"]:
        css_class = "badge-info"
        icon = "✦"

    return f'<span class="status-badge {css_class}">{icon} {label}</span>'


def render_status_badge(status: str, custom_label: str = None) -> None:
    """Directly render a status badge inside Streamlit page."""
    html = get_status_badge_html(status, custom_label)
    st.markdown(html, unsafe_allow_html=True)
