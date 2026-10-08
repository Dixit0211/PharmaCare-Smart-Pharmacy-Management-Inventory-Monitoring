"""Medicines catalog, category management, and physical batch inventory page."""

from datetime import date, timedelta
from typing import Optional, Dict, Any
import streamlit as st
import pandas as pd

from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.status_badge import render_status_badge, get_status_badge_html
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.components.data_table import render_paginated_table
from app.services.medicine_service import MedicineService
from app.services.category_service import CategoryService
from app.services.batch_service import BatchService
from app.core.exceptions import AppException, ValidationError, ConflictException

# Enforce authentication guard
if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/medication: Medicines Catalog & Inventory")
st.caption("Manage master pharmaceutical products, dosage forms, therapeutic categories, and batch inventory")

tab_catalog, tab_categories, tab_batches = st.tabs([
    ":material/pill: Master Medicines Catalog",
    ":material/category: Categories",
    ":material/inventory: Physical Batch Inventory",
])

# ==============================================================================
# TAB 1: MASTER MEDICINES CATALOG
# ==============================================================================
with tab_catalog:
    # Top KPI Metrics
    medicines_all = MedicineService.list_medicines()
    total_meds = len(medicines_all)
    total_units = sum(m["total_stock"] for m in medicines_all)
    low_stock_count = sum(1 for m in medicines_all if m["is_low_stock"])
    rx_count = sum(1 for m in medicines_all if m["prescription_required"])

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_metric_card("Total Products", str(total_meds), "Catalog master items", accent="teal", icon="💊")
    with k2:
        render_metric_card("Total Active Stock", f"{total_units:,}", "Units in physical batches", accent="green", icon="📦")
    with k3:
        render_metric_card("Low Stock Alerts", str(low_stock_count), "Below reorder threshold", accent="amber" if low_stock_count > 0 else "teal", icon="⚠️")
    with k4:
        render_metric_card("Prescription Only", str(rx_count), "Schedule H / Rx required", accent="blue", icon="📝")

    st.markdown("---")

    # Header Controls & Filter Bar
    c_btn, _, c_search = st.columns([2, 1, 3])
    with c_btn:
        if st.button("Add New Medicine", icon=":material/add_circle:", type="primary", use_container_width=True):
            add_medicine_dialog(current_user)

    with c_search:
        search_kw = st.text_input("Search catalog", placeholder="Search by name, generic, barcode...", label_visibility="collapsed")

    f1, f2, f3 = st.columns(3)
    with f1:
        cat_options = {"All Categories": None}
        for c in CategoryService.list_categories():
            cat_options[c["name"]] = c["id"]
        selected_cat_name = st.selectbox("Filter by Category", options=list(cat_options.keys()))
        selected_cat_id = cat_options[selected_cat_name]

    with f2:
        selected_rx_filter = st.selectbox("Prescription Requirement", options=["All", "Rx Required Only", "OTC Only"])
        rx_val = True if selected_rx_filter == "Rx Required Only" else (False if selected_rx_filter == "OTC Only" else None)

    with f3:
        selected_status = st.selectbox("Status", options=["All", "Active", "Inactive"])
        status_val = selected_status.lower() if selected_status != "All" else None

    # Filtered dataset
    filtered_medicines = MedicineService.list_medicines(
        search=search_kw,
        category_id=selected_cat_id,
        status=status_val,
        prescription_required=rx_val,
    )

    if not filtered_medicines:
        render_empty_state("No Medicines Found", "No medicines match your selected filters. Try clearing your search or add a new medicine.")
    else:
        # Display Medicines Table
        st.markdown(f"**Showing {len(filtered_medicines)} medicine(s):**")

        # Format rows for display
        table_rows = []
        for m in filtered_medicines:
            stock_display = f"{m['total_stock']} units"
            if m["is_low_stock"]:
                stock_display += " ⚠️ (Low)"

            table_rows.append({
                "ID": m["id"],
                "Medicine Name": m["name"],
                "Generic Name": m["generic_name"],
                "Category": m["category_name"],
                "Form & Strength": f"{m['dosage_form']} - {m['strength']}",
                "Price": f"₹{m['selling_price']:.2f}",
                "Available Stock": stock_display,
                "Min Stock": m["min_stock"],
                "Rx Req.": "Yes (Rx)" if m["prescription_required"] else "No (OTC)",
                "Status": m["status"].capitalize(),
            })

        st.dataframe(
            pd.DataFrame(table_rows),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Medicine Details & Batch Inspection")
        med_choices = {f"{m['name']} ({m['strength']}) - Stock: {m['total_stock']}": m["id"] for m in filtered_medicines}
        selected_med_label = st.selectbox("Select medicine to inspect batches & actions:", options=list(med_choices.keys()))
        selected_med_id = med_choices[selected_med_label]

        if selected_med_id:
            med_detail = MedicineService.get_medicine(selected_med_id)
            
            with st.container(border=True):
                col_d1, col_d2, col_d3 = st.columns([2, 2, 2])
                with col_d1:
                    st.markdown(f"#### {med_detail['name']}")
                    st.caption(f"Generic: **{med_detail['generic_name']}**")
                    st.write(f"🏷️ Category: **{med_detail['category_name']}**")
                    st.write(f"🏭 Manufacturer: **{med_detail['manufacturer'] or '-'}**")
                with col_d2:
                    st.write(f"📦 Dosage Form: **{med_detail['dosage_form']}**")
                    st.write(f"💪 Strength: **{med_detail['strength']}**")
                    st.write(f"💰 Selling Price: **₹{med_detail['selling_price']:.2f}**")
                    st.write(f"🔢 Barcode: **`{med_detail['barcode'] or 'N/A'}`**")
                with col_d3:
                    st.write(f"📊 Available Stock: **{med_detail['total_stock']} units**")
                    st.write(f"⚠️ Min Stock Threshold: **{med_detail['min_stock']} units**")
                    st.write(f"📋 Schedule H Rx: **{'Required' if med_detail['prescription_required'] else 'Not Required (OTC)'}**")
                    render_status_badge(med_detail["status"])

                st.markdown("##### Associated Batches:")
                batches = med_detail["batches"]
                if not batches:
                    st.info("No batches found for this medicine. Add a batch in the 'Physical Batch Inventory' tab.")
                else:
                    batch_display = []
                    for b in batches:
                        batch_display.append({
                            "Batch No": b["batch_no"],
                            "Expiry Date": b["expiry_date"],
                            "Days Remaining": f"{b['days_remaining']} days" if b['days_remaining'] >= 0 else f"Expired ({abs(b['days_remaining'])}d ago)",
                            "Quantity": b["quantity"],
                            "Purchase Price": f"₹{b['purchase_price']:.2f}",
                            "Status": b["status"].replace("_", " ").title(),
                        })
                    st.dataframe(pd.DataFrame(batch_display), use_container_width=True, hide_index=True)

                col_act1, col_act2, _ = st.columns([1.5, 1.5, 3])
                with col_act1:
                    if st.button("Edit Medicine Info", icon=":material/edit:", key=f"edit_btn_{selected_med_id}"):
                        edit_medicine_dialog(current_user, med_detail)
                with col_act2:
                    if st.button("Deactivate / Delete", icon=":material/delete:", type="secondary", key=f"del_btn_{selected_med_id}"):
                        delete_medicine_dialog(current_user, med_detail)


# ==============================================================================
# TAB 2: CATEGORY MANAGEMENT
# ==============================================================================
with tab_categories:
    st.markdown("### Therapeutic Category Management")
    st.caption("Organize products by medical classifications to streamline inventory and searching")

    c_c_btn, _ = st.columns([2, 4])
    with c_c_btn:
        if st.button("Add New Category", icon=":material/add:", type="primary", use_container_width=True):
            add_category_dialog(current_user)

    categories_list = CategoryService.list_categories()
    if not categories_list:
        render_empty_state("No Categories", "No categories defined yet.")
    else:
        c_df = pd.DataFrame([
            {
                "Category ID": c["id"],
                "Category Name": c["name"],
                "Description": c["description"],
                "Linked Medicines": f"{c['medicine_count']} products",
                "Created Date": c["created_at"],
            }
            for c in categories_list
        ])
        st.dataframe(c_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Category Actions")
        cat_choices = {f"{c['name']} ({c['medicine_count']} items)": c for c in categories_list}
        selected_cat_label = st.selectbox("Select category to edit or delete:", options=list(cat_choices.keys()), key="cat_action_select")
        sel_cat_obj = cat_choices[selected_cat_label]

        ca1, ca2, _ = st.columns([1.5, 1.5, 3])
        with ca1:
            if st.button("Edit Category", icon=":material/edit:", key="edit_cat_btn"):
                edit_category_dialog(current_user, sel_cat_obj)
        with ca2:
            if st.button("Delete Category", icon=":material/delete:", type="secondary", key="del_cat_btn"):
                delete_category_dialog(current_user, sel_cat_obj)


# ==============================================================================
# TAB 3: PHYSICAL BATCH INVENTORY
# ==============================================================================
with tab_batches:
    st.markdown("### Physical Batch Inventory & FEFO Tracking")
    st.caption("Manage batches, inspect expiry dates, and record audited physical stock adjustments")

    b_col_add, b_col_filter = st.columns([2, 3])
    with b_col_add:
        if st.button("Add New Physical Batch", icon=":material/add_box:", type="primary", use_container_width=True):
            add_batch_dialog(current_user)

    with b_col_filter:
        b_med_choices = {"All Medicines": None}
        for m in medicines_all:
            b_med_choices[f"{m['name']} ({m['strength']})"] = m["id"]
        sel_b_med = st.selectbox("Filter batches by medicine:", options=list(b_med_choices.keys()), key="batch_filter_med")
        sel_b_med_id = b_med_choices[sel_b_med]

    all_batches = BatchService.list_batches(medicine_id=sel_b_med_id)

    if not all_batches:
        render_empty_state("No Batches Recorded", "There are no physical batches matching the selection.")
    else:
        b_table = []
        for b in all_batches:
            b_table.append({
                "Batch ID": b["id"],
                "Medicine": b["medicine_name"],
                "Batch Number": b["batch_no"],
                "Expiry Date": b["expiry_date"],
                "Days Left": f"{b['days_remaining']} days" if b['days_remaining'] >= 0 else f"EXPIRED ({abs(b['days_remaining'])}d ago)",
                "Physical Quantity": f"{b['quantity']} units",
                "Purchase Price": f"₹{b['purchase_price']:.2f}",
                "Status": b["status"].replace("_", " ").title(),
            })

        st.dataframe(pd.DataFrame(b_table), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Batch Stock Adjustment & Auditing")
        batch_opts = {f"Batch {b['batch_no']} ({b['medicine_name']}) - Qty: {b['quantity']}": b for b in all_batches}
        sel_batch_label = st.selectbox("Select batch to adjust or manage:", options=list(batch_opts.keys()), key="batch_adj_select")
        sel_batch = batch_opts[sel_batch_label]

        ba1, ba2, _ = st.columns([2, 1.5, 2.5])
        with ba1:
            if st.button("Adjust Stock (Audit)", icon=":material/tune:", key="adj_stock_btn"):
                adjust_batch_dialog(current_user, sel_batch)
        with ba2:
            if st.button("Edit Batch Info", icon=":material/edit:", key="edit_batch_btn"):
                edit_batch_dialog(current_user, sel_batch)


# ==============================================================================
# MODAL DIALOGS (MEDICINES, CATEGORIES, BATCHES)
# ==============================================================================

@st.dialog("Add New Medicine")
def add_medicine_dialog(curr_user):
    """Modal dialog to register a new medicine master record."""
    cats = CategoryService.list_categories()
    if not cats:
        st.error("Please create at least one Category before adding medicines.")
        return

    cat_map = {c["name"]: c["id"] for c in cats}

    with st.form("add_med_form"):
        st.write("Enter product specifications:")
        name = st.text_input("Medicine Brand Name *", placeholder="e.g. Paracetamol 500mg")
        generic = st.text_input("Generic Chemical Name *", placeholder="e.g. Acetaminophen")
        c1, c2 = st.columns(2)
        with c1:
            cat_name = st.selectbox("Therapeutic Category *", options=list(cat_map.keys()))
            dosage = st.selectbox("Dosage Form *", options=["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Inhaler"])
            selling_p = st.number_input("Selling Price (₹) *", min_value=0.0, value=25.0, step=1.0)
        with c2:
            strength = st.text_input("Strength *", placeholder="e.g. 500mg, 10mg/ml")
            min_stk = st.number_input("Min Reorder Stock *", min_value=0, value=15, step=5)
            barcode = st.text_input("Barcode (optional)", placeholder="e.g. 890103000101")

        mfr = st.text_input("Manufacturer", placeholder="e.g. Abbott Healthcare")
        brand = st.text_input("Brand", placeholder="e.g. Calpol")
        rx_req = st.checkbox("Requires Doctor Prescription (Schedule H / X)")

        submit = st.form_submit_button("Save Medicine", type="primary", use_container_width=True)
        if submit:
            try:
                MedicineService.create_medicine(
                    current_user=curr_user,
                    data={
                        "name": name,
                        "generic_name": generic,
                        "category_id": cat_map[cat_name],
                        "dosage_form": dosage,
                        "strength": strength,
                        "selling_price": selling_p,
                        "min_stock": min_stk,
                        "barcode": barcode,
                        "manufacturer": mfr,
                        "brand": brand,
                        "prescription_required": rx_req,
                    },
                )
                st.toast(f"Medicine '{name}' created successfully!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Edit Medicine")
def edit_medicine_dialog(curr_user, med_data):
    """Modal dialog to edit existing medicine details."""
    cats = CategoryService.list_categories()
    cat_map = {c["name"]: c["id"] for c in cats}
    cat_names = list(cat_map.keys())

    curr_cat_idx = 0
    for idx, cname in enumerate(cat_names):
        if cat_map[cname] == med_data["category_id"]:
            curr_cat_idx = idx
            break

    dosage_forms = ["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Inhaler"]
    dosage_idx = dosage_forms.index(med_data["dosage_form"]) if med_data["dosage_form"] in dosage_forms else 0

    with st.form("edit_med_form"):
        st.write(f"Editing **{med_data['name']}**:")
        name = st.text_input("Medicine Name *", value=med_data["name"])
        generic = st.text_input("Generic Chemical Name *", value=med_data["generic_name"])
        c1, c2 = st.columns(2)
        with c1:
            cat_name = st.selectbox("Category *", options=cat_names, index=curr_cat_idx)
            dosage = st.selectbox("Dosage Form *", options=dosage_forms, index=dosage_idx)
            selling_p = st.number_input("Selling Price (₹) *", min_value=0.0, value=float(med_data["selling_price"]), step=1.0)
        with c2:
            strength = st.text_input("Strength *", value=med_data["strength"])
            min_stk = st.number_input("Min Reorder Stock *", min_value=0, value=int(med_data["min_stock"]), step=5)
            barcode = st.text_input("Barcode", value=med_data["barcode"] or "")

        mfr = st.text_input("Manufacturer", value=med_data["manufacturer"] or "")
        brand = st.text_input("Brand", value=med_data["brand"] or "")
        status = st.selectbox("Status", options=["active", "inactive"], index=0 if med_data["status"] == "active" else 1)
        rx_req = st.checkbox("Requires Doctor Prescription (Schedule H)", value=bool(med_data["prescription_required"]))

        submit = st.form_submit_button("Update Medicine", type="primary", use_container_width=True)
        if submit:
            try:
                MedicineService.update_medicine(
                    current_user=curr_user,
                    medicine_id=med_data["id"],
                    data={
                        "name": name,
                        "generic_name": generic,
                        "category_id": cat_map[cat_name],
                        "dosage_form": dosage,
                        "strength": strength,
                        "selling_price": selling_p,
                        "min_stock": min_stk,
                        "barcode": barcode,
                        "manufacturer": mfr,
                        "brand": brand,
                        "prescription_required": rx_req,
                        "status": status,
                    },
                )
                st.toast("Medicine updated successfully!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Delete / Deactivate Medicine")
def delete_medicine_dialog(curr_user, med_data):
    """Confirmation modal for deactivating or deleting a medicine."""
    st.warning(f"Are you sure you want to remove **{med_data['name']}** from active service?")
    st.caption("If this medicine has historical sales records, it will be safely deactivated to protect audit trails.")
    
    col_c, col_d = st.columns(2)
    with col_c:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col_d:
        if st.button("Confirm Delete", type="primary", use_container_width=True):
            try:
                MedicineService.delete_medicine(curr_user, med_data["id"])
                st.toast(f"Medicine '{med_data['name']}' processed successfully.", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Add Category")
def add_category_dialog(curr_user):
    """Modal to add a new category."""
    with st.form("add_cat_form"):
        name = st.text_input("Category Name *", placeholder="e.g. Antibiotics, Antidiabetic")
        desc = st.text_area("Description", placeholder="Medical classification details...")
        submit = st.form_submit_button("Save Category", type="primary", use_container_width=True)
        if submit:
            try:
                CategoryService.create_category(curr_user, name, desc)
                st.toast(f"Category '{name}' created!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Edit Category")
def edit_category_dialog(curr_user, cat_obj):
    """Modal to edit a category."""
    with st.form("edit_cat_form"):
        name = st.text_input("Category Name *", value=cat_obj["name"])
        desc = st.text_area("Description", value=cat_obj["description"])
        submit = st.form_submit_button("Update Category", type="primary", use_container_width=True)
        if submit:
            try:
                CategoryService.update_category(curr_user, cat_obj["id"], name, desc)
                st.toast("Category updated!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Delete Category")
def delete_category_dialog(curr_user, cat_obj):
    """Confirmation modal to delete a category."""
    st.write(f"Delete category **{cat_obj['name']}**?")
    st.caption("Categories currently associated with medicines cannot be deleted.")

    if st.button("Confirm Delete", type="primary", use_container_width=True):
        try:
            CategoryService.delete_category(curr_user, cat_obj["id"])
            st.toast("Category deleted successfully!", icon="✅")
            st.rerun()
        except ConflictException as ce:
            st.error(ce.message)
        except AppException as e:
            st.error(e.message)


@st.dialog("Add Physical Batch")
def add_batch_dialog(curr_user):
    """Modal to register a new physical batch."""
    meds = MedicineService.list_medicines()
    if not meds:
        st.error("Please add medicines first.")
        return

    med_map = {f"{m['name']} ({m['strength']})": m["id"] for m in meds}

    with st.form("add_batch_form"):
        st.write("Enter physical batch intake details:")
        med_label = st.selectbox("Medicine *", options=list(med_map.keys()))
        batch_no = st.text_input("Batch Number *", placeholder="e.g. PARA-2024-B3").upper()
        
        c1, c2 = st.columns(2)
        with c1:
            expiry_d = st.date_input("Expiry Date *", value=date.today() + timedelta(days=365))
            qty = st.number_input("Initial Quantity (Units) *", min_value=1, value=50, step=10)
        with c2:
            p_price = st.number_input("Purchase Price Per Unit (₹) *", min_value=0.0, value=15.0, step=1.0)

        submit = st.form_submit_button("Save Batch to Inventory", type="primary", use_container_width=True)
        if submit:
            try:
                BatchService.create_batch(
                    current_user=curr_user,
                    medicine_id=med_map[med_label],
                    batch_no=batch_no,
                    expiry_date_val=expiry_d,
                    quantity=int(qty),
                    purchase_price=float(p_price),
                )
                st.toast(f"Batch '{batch_no}' added to stock!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Adjust Physical Batch Stock")
def adjust_batch_dialog(curr_user, batch_obj):
    """Modal to record an audited stock discrepancy or damage adjustment."""
    st.write(f"Stock Audit for **{batch_obj['medicine_name']}** (Batch: **{batch_obj['batch_no']}**)")
    st.caption(f"Current recorded stock: **{batch_obj['quantity']} units**")

    with st.form("adj_stock_form"):
        new_q = st.number_input("Correct Physical Count (Units) *", min_value=0, value=int(batch_obj["quantity"]), step=1)
        reason = st.selectbox(
            "Adjustment Reason *",
            options=[
                "Routine physical count reconciliation",
                "Damaged / broken container discarded",
                "Quarantined / sample inspection",
                "Supplier return / discrepancy",
                "Other physical audit correction",
            ],
        )
        custom_notes = st.text_input("Additional Notes", placeholder="e.g. Discovered 2 crushed strips during monthly audit")

        submit = st.form_submit_button("Record Stock Adjustment", type="primary", use_container_width=True)
        if submit:
            try:
                full_reason = f"{reason} - {custom_notes}" if custom_notes else reason
                BatchService.adjust_batch_stock(
                    current_user=curr_user,
                    batch_id=batch_obj["id"],
                    new_quantity=int(new_q),
                    reason=full_reason,
                )
                st.toast("Stock adjustment recorded and audited!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Edit Batch Details")
def edit_batch_dialog(curr_user, batch_obj):
    """Modal to edit batch parameters."""
    with st.form("edit_batch_form"):
        st.write(f"Edit Batch **{batch_obj['batch_no']}** ({batch_obj['medicine_name']}):")
        
        c1, c2 = st.columns(2)
        with c1:
            try:
                exp_date_val = date.fromisoformat(batch_obj["expiry_date"])
            except Exception:
                exp_date_val = date.today() + timedelta(days=365)

            new_exp = st.date_input("Expiry Date *", value=exp_date_val)
            new_qty = st.number_input("Quantity *", min_value=0, value=int(batch_obj["quantity"]), step=1)
        with c2:
            new_price = st.number_input("Purchase Price (₹) *", min_value=0.0, value=float(batch_obj["purchase_price"]), step=1.0)

        submit = st.form_submit_button("Update Batch", type="primary", use_container_width=True)
        if submit:
            try:
                BatchService.update_batch(
                    current_user=curr_user,
                    batch_id=batch_obj["id"],
                    quantity=int(new_qty),
                    purchase_price=float(new_price),
                    expiry_date_val=new_exp,
                )
                st.toast("Batch updated successfully!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)
