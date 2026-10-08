"""Global CSS design system injection for professional white cream / vanilla UI aesthetics."""

import streamlit as st


def inject_custom_styles() -> None:
    """Inject tailored CSS for a high-end, modern white cream / vanilla clinical UI."""
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Overall Application Background & Base Typography */
    .stApp {
        background-color: #FAF8F5 !important;
        color: #1C1917 !important;
    }

    /* Headings Styling */
    h1, h2, h3, h4, h5, h6 {
        color: #1C1917 !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    /* Main Container Spacing & Layout */
    .main .block-container {
        padding-top: 1.75rem;
        padding-bottom: 3rem;
        max-width: 1350px;
    }

    /* Sidebar Vanilla Cream Palette */
    [data-testid="stSidebar"] {
        background-color: #F3EFEA !important;
        border-right: 1px solid #E7E0D5 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
    [data-testid="stSidebar"] label {
        color: #292524 !important;
    }

    /* Sidebar Navigation item hover styling */
    [data-testid="stSidebarNav"] a {
        border-radius: 10px !important;
        padding: 0.5rem 0.75rem !important;
        transition: all 0.2s ease !important;
        color: #44403C !important;
        font-weight: 500 !important;
    }

    [data-testid="stSidebarNav"] a:hover {
        background-color: #EAE4DC !important;
        color: #0F766E !important;
    }

    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background-color: #FFFFFF !important;
        color: #0F766E !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 8px rgba(120, 100, 80, 0.06) !important;
        border: 1px solid #E5DFD5 !important;
    }

    /* User Profile Chip inside Sidebar */
    .user-profile-chip {
        background: #FFFFFF !important;
        border: 1px solid #E7E0D5 !important;
        border-radius: 14px !important;
        padding: 0.9rem !important;
        margin-bottom: 1.25rem !important;
        box-shadow: 0 4px 14px rgba(120, 100, 80, 0.05) !important;
    }

    .user-profile-name {
        font-weight: 700 !important;
        color: #1C1917 !important;
        font-size: 0.95rem !important;
    }

    .user-profile-email {
        font-size: 0.75rem !important;
        color: #78716C !important;
    }

    /* Professional Cream & White Cards */
    .pharma-card, div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"] > div {
        background: #FFFFFF !important;
        border: 1px solid #EBE5DC !important;
        border-radius: 14px !important;
        padding: 1.35rem 1.5rem !important;
        box-shadow: 0 4px 20px -2px rgba(80, 70, 60, 0.04), 0 2px 6px -1px rgba(80, 70, 60, 0.02) !important;
        margin-bottom: 1.25rem !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    .pharma-card:hover {
        box-shadow: 0 10px 25px -4px rgba(80, 70, 60, 0.08), 0 4px 10px -2px rgba(80, 70, 60, 0.04) !important;
        border-color: #D6CEC0 !important;
    }

    /* Metric KPI Card Component */
    .metric-container {
        background: #FFFFFF !important;
        border: 1px solid #EBE5DC !important;
        border-radius: 14px !important;
        padding: 1.25rem !important;
        box-shadow: 0 4px 16px rgba(120, 100, 80, 0.04) !important;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        border-left: 4px solid #0F766E !important;
        transition: all 0.25s ease !important;
    }

    .metric-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(120, 100, 80, 0.09) !important;
    }

    .metric-container.accent-amber { border-left-color: #D97706 !important; }
    .metric-container.accent-red { border-left-color: #E11D48 !important; }
    .metric-container.accent-blue { border-left-color: #2563EB !important; }
    .metric-container.accent-green { border-left-color: #059669 !important; }

    .metric-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }

    .metric-label {
        font-size: 0.8rem !important;
        font-weight: 700 !important;
        color: #78716C !important;
        text-transform: uppercase;
        letter-spacing: 0.05em !important;
    }

    .metric-value {
        font-size: 1.85rem !important;
        font-weight: 800 !important;
        color: #1C1917 !important;
        line-height: 1.15 !important;
    }

    .metric-subtext {
        font-size: 0.82rem !important;
        color: #78716C !important;
        font-weight: 500 !important;
        margin-top: 0.35rem !important;
    }

    /* Status Badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.28rem 0.72rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        white-space: nowrap;
    }

    .badge-safe {
        background-color: #E6F4EA !important;
        color: #137333 !important;
        border: 1px solid #CEEAD6 !important;
    }

    .badge-warning {
        background-color: #FEF3C7 !important;
        color: #92400E !important;
        border: 1px solid #FDE68A !important;
    }

    .badge-critical {
        background-color: #FEE2E2 !important;
        color: #991B1B !important;
        border: 1px solid #FECACA !important;
    }

    .badge-info {
        background-color: #E0F2FE !important;
        color: #075985 !important;
        border: 1px solid #BAE6FD !important;
    }

    .badge-neutral {
        background-color: #F3EFEA !important;
        color: #57534E !important;
        border: 1px solid #E7E0D5 !important;
    }

    /* Custom Form Control & Input Elements */
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="textarea"] > div {
        background-color: #FFFFFF !important;
        border: 1px solid #E5DFD5 !important;
        border-radius: 10px !important;
        color: #1C1917 !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }

    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: #0F766E !important;
        box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.15) !important;
    }

    /* Buttons Styling */
    div.stButton > button:first-child {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0F766E 0%, #115E59 100%) !important;
        border: none !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.22) !important;
    }

    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #115E59 0%, #0F766E 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(15, 118, 110, 0.35) !important;
    }

    div.stButton > button[kind="secondary"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E5DFD5 !important;
        color: #292524 !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02) !important;
    }

    div.stButton > button[kind="secondary"]:hover {
        background-color: #F5F1EB !important;
        border-color: #D6CEC0 !important;
        transform: translateY(-1px) !important;
    }

    /* Tabs Component Styling */
    [data-baseweb="tab-list"] {
        background-color: transparent !important;
        gap: 0.5rem !important;
        border-bottom: 2px solid #E7E0D5 !important;
    }

    [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        font-weight: 600 !important;
        color: #78716C !important;
        padding: 0.6rem 1rem !important;
    }

    [aria-selected="true"] {
        color: #0F766E !important;
        border-bottom: 3px solid #0F766E !important;
        background-color: #F8F5F0 !important;
    }

    /* Data Frame Clean Table */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important;
        border: 1px solid #EBE5DC !important;
        overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(120, 100, 80, 0.03) !important;
    }

    /* Glass Header Card Banner */
    .pharma-header-banner {
        background: linear-gradient(135deg, #FFFFFF 0%, #F5F1EB 100%) !important;
        border: 1px solid #EBE5DC !important;
        border-radius: 16px !important;
        padding: 1.5rem 1.8rem !important;
        box-shadow: 0 4px 20px -2px rgba(80, 70, 60, 0.05) !important;
        margin-bottom: 1.5rem !important;
    }

    .pharma-header-banner h2 {
        margin: 0 !important;
        color: #1C1917 !important;
        font-weight: 800 !important;
        font-size: 1.65rem !important;
    }

    .pharma-header-banner p {
        margin: 0.35rem 0 0 0 !important;
        color: #78716C !important;
        font-size: 0.95rem !important;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
