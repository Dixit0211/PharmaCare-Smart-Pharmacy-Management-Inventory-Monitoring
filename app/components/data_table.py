"""Reusable paginated data table component with search and sorting."""

import math
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st


def render_paginated_table(
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    key_prefix: str = "table",
    default_page_size: int = 10,
    search_columns: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Render an interactive, paginated, searchable data table."""
    if not data:
        st.info("No records available to display.")
        return None

    df = pd.DataFrame(data)

    # Search filter bar
    c1, c2 = st.columns([3, 1])
    with c1:
        search_query = st.text_input(
            "Search records",
            placeholder="Type keyword to filter...",
            key=f"{key_prefix}_search",
            label_visibility="collapsed",
        )
    with c2:
        page_size = st.selectbox(
            "Rows per page",
            options=[10, 25, 50, 100],
            index=[10, 25, 50, 100].index(default_page_size) if default_page_size in [10, 25, 50, 100] else 0,
            key=f"{key_prefix}_page_size",
            label_visibility="collapsed",
        )

    # Apply search filter
    if search_query:
        query_str = str(search_query).strip().lower()
        cols_to_search = search_columns if search_columns else df.columns.tolist()

        mask = df[cols_to_search].astype(str).apply(
            lambda col: col.str.lower().str.contains(query_str, regex=False, na=False)
        ).any(axis=1)
        filtered_df = df[mask]
    else:
        filtered_df = df

    total_records = len(filtered_df)
    if total_records == 0:
        st.warning(f"No records match '{search_query}'.")
        return None

    total_pages = max(1, math.ceil(total_records / page_size))

    # Page navigation controls
    p1, p2, p3 = st.columns([2, 2, 2])
    with p1:
        st.caption(f"Showing **{min(total_records, 1)}** to **{min(page_size, total_records)}** of **{total_records}** entries")
    with p3:
        current_page = st.number_input(
            f"Page (of {total_pages})",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key=f"{key_prefix}_curr_page",
        )

    # Slice DataFrame
    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = filtered_df.iloc[start_idx:end_idx]

    if columns:
        valid_cols = [c for c in columns if c in page_df.columns]
        page_df = page_df[valid_cols]

    st.dataframe(
        page_df,
        use_container_width=True,
        hide_index=True,
    )

    return None
