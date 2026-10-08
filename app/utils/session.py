"""Session state management and inactivity timeout enforcement for Streamlit."""

import time
from typing import Optional, Dict, Any
import streamlit as st
from app.core.config import settings
from app.services.audit_service import AuditService


def init_session() -> None:
    """Initialize default keys in Streamlit session state if not present."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "last_activity" not in st.session_state:
        st.session_state["last_activity"] = time.time()
    if "cart" not in st.session_state:
        st.session_state["cart"] = []
    if "is_submitting" not in st.session_state:
        st.session_state["is_submitting"] = False


def login_user(user_dict: Dict[str, Any]) -> None:
    """Store user in session state and update activity timestamp."""
    st.session_state["authenticated"] = True
    st.session_state["user"] = user_dict
    st.session_state["last_activity"] = time.time()
    st.session_state["cart"] = []


def logout_user() -> None:
    """Clear user session state and log audit record."""
    user = st.session_state.get("user")
    if user:
        AuditService.log_action(
            user_id=user.get("id"),
            username=user.get("username", "unknown"),
            action="LOGOUT",
            module="AUTH",
            description="User logged out",
        )
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["cart"] = []
    st.session_state["last_activity"] = 0


def get_current_user() -> Optional[Dict[str, Any]]:
    """Return currently authenticated user payload from session state."""
    init_session()
    if st.session_state.get("authenticated", False):
        return st.session_state.get("user")
    return None


def is_authenticated() -> bool:
    """Check if session is currently authenticated."""
    init_session()
    return bool(st.session_state.get("authenticated", False) and st.session_state.get("user"))


def is_admin() -> bool:
    """Check if current user is an Administrator."""
    user = get_current_user()
    return bool(user and user.get("role", "").lower() == "admin")


def is_pharmacist() -> bool:
    """Check if current user is a Pharmacist."""
    user = get_current_user()
    return bool(user and user.get("role", "").lower() == "pharmacist")


def update_activity() -> None:
    """Update last activity timestamp to prevent premature timeout."""
    st.session_state["last_activity"] = time.time()


def check_session_timeout(timeout_minutes: Optional[int] = None) -> bool:
    """
    Check if the user session has timed out due to inactivity.
    Returns True if session timed out and was reset.
    """
    if not is_authenticated():
        return False

    limit_minutes = timeout_minutes or settings.SESSION_EXPIRE_MINUTES
    max_idle_seconds = limit_minutes * 60
    current_time = time.time()
    last_act = st.session_state.get("last_activity", current_time)

    if (current_time - last_act) > max_idle_seconds:
        user = st.session_state.get("user")
        if user:
            AuditService.log_action(
                user_id=user.get("id"),
                username=user.get("username", "unknown"),
                action="TIMEOUT",
                module="AUTH",
                description=f"Session timed out after {limit_minutes} mins inactivity",
            )
        logout_user()
        return True

    update_activity()
    return False
