"""Global CSS design system injection for hospital-grade UI aesthetics."""

import streamlit as st


def inject_custom_styles() -> None:
    """Inject tailored CSS for clinical hospital-grade UI aesthetics."""
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Background and Layout */
    .stApp {
        background-color: #F8FAFC;
    }

    /* Main Container Padding */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1350px;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #1E293B;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
    [data-testid="stSidebar"] label {
        color: #E2E8F0 !important;
    }

    /* Card Containers */
    .pharma-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.05), 0 1px 2px -1px rgba(15, 23, 42, 0.05);
        margin-bottom: 1.25rem;
        transition: all 0.2s ease-in-out;
    }

    .pharma-card:hover {
        box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.08);
        border-color: #CBD5E1;
    }

    /* Metric Card Component */
    .metric-container {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        border-left: 4px solid #0D9488;
    }

    .metric-container.accent-amber { border-left-color: #F59E0B; }
    .metric-container.accent-red { border-left-color: #EF4444; }
    .metric-container.accent-blue { border-left-color: #3B82F6; }
    .metric-container.accent-green { border-left-color: #10B981; }

    .metric-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }

    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0F172A;
        line-height: 1.2;
    }

    .metric-subtext {
        font-size: 0.8rem;
        color: #64748B;
        margin-top: 0.25rem;
    }

    /* Status Badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        white-space: nowrap;
    }

    .badge-safe {
        background-color: #DEF7EC;
        color: #03543F;
        border: 1px solid #BCF0DA;
    }

    .badge-warning {
        background-color: #FEF08A;
        color: #713F12;
        border: 1px solid #FDE047;
    }

    .badge-critical {
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }

    .badge-info {
        background-color: #E0F2FE;
        color: #075985;
        border: 1px solid #BAE6FD;
    }

    .badge-neutral {
        background-color: #F1F5F9;
        color: #475569;
        border: 1px solid #E2E8F0;
    }

    /* User Profile Chip in Sidebar */
    .user-profile-chip {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 0.85rem;
        margin-bottom: 1.25rem;
    }

    .user-profile-name {
        font-weight: 600;
        color: #F8FAFC;
        font-size: 0.95rem;
    }

    .user-profile-email {
        font-size: 0.75rem;
        color: #94A3B8;
    }

    /* Form styling and buttons */
    div.stButton > button:first-child {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.15s ease-in-out;
    }

    div.stButton > button[kind="primary"] {
        background-color: #0D9488;
        border-color: #0D9488;
        color: #FFFFFF;
    }

    div.stButton > button[kind="primary"]:hover {
        background-color: #0F766E;
        border-color: #0F766E;
    }

    /* Clean Streamlit table responsiveness */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        border: 1px solid #E2E8F0;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
