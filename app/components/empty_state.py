"""Empty state indicator for empty tables, search results, and filters."""

from typing import Optional
import streamlit as st


def render_empty_state(
    title: str = "No records found",
    message: str = "There are no matching items to display at this time.",
    icon: str = "📋",
    action_text: Optional[str] = None,
) -> bool:
    """Render a clean empty state card with optional action button."""
    st.markdown(
        f"""
        <div style="
            text-align: center;
            padding: 3rem 1.5rem;
            background: #FFFFFF;
            border: 2px dashed #D6CEC0;
            border-radius: 14px;
            margin: 1.5rem 0;
            box-shadow: 0 4px 16px rgba(120, 100, 80, 0.03);
        ">
            <div style="font-size: 2.75rem; margin-bottom: 0.75rem;">{icon}</div>
            <h4 style="color: #1C1917; margin-bottom: 0.35rem; font-weight: 700;">{title}</h4>
            <p style="color: #78716C; font-size: 0.92rem; max-width: 420px; margin: 0 auto 1rem auto; font-weight: 500;">{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if action_text:
        return st.button(action_text, key=f"empty_state_btn_{title}")
    return False
