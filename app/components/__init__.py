"""UI components for PharmaCare."""

from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.status_badge import render_status_badge, get_status_badge_html
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.components.data_table import render_paginated_table

__all__ = [
    "inject_custom_styles",
    "render_sidebar",
    "render_status_badge",
    "get_status_badge_html",
    "render_metric_card",
    "render_empty_state",
    "render_paginated_table",
]
