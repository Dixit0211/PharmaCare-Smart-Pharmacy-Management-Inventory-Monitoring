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
            border: 2px dashed #CBD5E1;
            border-radius: 12px;
            margin: 1.5rem 0;
        ">
            <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">{icon}</div>
            <h4 style="color: #1E293B; margin-bottom: 0.25rem; font-weight: 600;">{title}</h4>
            <p style="color: #64748B; font-size: 0.9rem; max-width: 400px; margin: 0 auto 1rem auto;">{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if action_text:
        return st.button(action_text, key=f"empty_state_btn_{title}")
    return False
