"""Wholesale Suppliers and Distributors management page."""

from typing import Dict, Any
import streamlit as st
import pandas as pd

from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.services.supplier_service import SupplierService
from app.core.exceptions import AppException, ConflictException

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/local_shipping: Wholesale Suppliers & Distributors")
st.caption("Manage registered pharmaceutical distributors, contact records, tax numbers, and procurement spend")

# Fetch suppliers
all_suppliers = SupplierService.list_suppliers()
total_suppliers = len(all_suppliers)
total_spend = sum(s["total_procured"] for s in all_suppliers)
total_orders = sum(s["purchase_count"] for s in all_suppliers)

# Summary KPI Cards
k1, k2, k3 = st.columns(3)
with k1:
    render_metric_card("Registered Vendors", str(total_suppliers), "Active wholesale distributors", accent="teal", icon="🏢")
with k2:
    render_metric_card("Inward Invoices", str(total_orders), "Procurement purchase orders", accent="blue", icon="📦")
with k3:
    render_metric_card("Total Procurement Spend", f"₹{total_spend:,.2f}", "Cumulative vendor expenditure", accent="green", icon="💰")

st.markdown("---")

c_btn, _, c_search = st.columns([2, 1, 3])
with c_btn:
    if st.button("Add New Supplier", icon=":material/person_add:", type="primary", use_container_width=True):
        add_supplier_dialog(current_user)

with c_search:
    search_q = st.text_input("Search suppliers", placeholder="Search by name, contact, phone, GST...", label_visibility="collapsed")

# Filtered list
suppliers = SupplierService.list_suppliers(search=search_q)

if not suppliers:
    render_empty_state("No Suppliers Found", "No vendors match your search criteria. Try modifying your search or register a new supplier.")
else:
    s_table = []
    for s in suppliers:
        s_table.append({
            "Supplier ID": s["id"],
            "Company / Vendor Name": s["name"],
            "Contact Person": s["contact_person"],
            "Phone Number": s["phone"],
            "Email Address": s["email"],
            "GST Number": s["gst_number"],
            "Orders": f"{s['purchase_count']} orders",
            "Total Procured": f"₹{s['total_procured']:,.2f}",
        })

    st.dataframe(pd.DataFrame(s_table), use_container_width=True, hide_index=True)

    st.markdown("### Supplier Profile & Purchase History")
    sup_choices = {f"{s['name']} (Spend: ₹{s['total_procured']:,.2f})": s["id"] for s in suppliers}
    sel_sup_label = st.selectbox("Select supplier to inspect history & manage:", options=list(sup_choices.keys()))
    sel_sup_id = sup_choices[sel_sup_label]

    if sel_sup_id:
        sup_data = SupplierService.get_supplier(sel_sup_id)
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"#### {sup_data['name']}")
                st.caption(f"Contact Person: **{sup_data['contact_person'] or 'N/A'}**")
                st.write(f"📞 Phone: **{sup_data['phone']}**")
                st.write(f"✉️ Email: **{sup_data['email'] or 'N/A'}**")
            with col2:
                st.write(f"🏢 GST Number: **`{sup_data['gst_number'] or 'N/A'}`**")
                st.write(f"📍 Address: **{sup_data['address'] or 'N/A'}**")
                st.write(f"📦 Total Invoices: **{len(sup_data['purchases'])} invoices**")

            st.markdown("##### Inward Purchase Invoices from this Vendor:")
            if not sup_data["purchases"]:
                st.info("No purchase orders recorded yet for this supplier.")
            else:
                p_rows = [
                    {
                        "Invoice No": p["invoice_no"],
                        "Date": p["purchase_date"],
                        "Amount": f"₹{p['total_amount']:,.2f}",
                        "Status": p["status"].capitalize(),
                    }
                    for p in sup_data["purchases"]
                ]
                st.dataframe(pd.DataFrame(p_rows), use_container_width=True, hide_index=True)

            col_act1, col_act2, _ = st.columns([1.5, 1.5, 3])
            with col_act1:
                if st.button("Edit Supplier Profile", icon=":material/edit:", key=f"edit_sup_btn_{sel_sup_id}"):
                    edit_supplier_dialog(current_user, sup_data)
            with col_act2:
                if st.button("Delete Supplier", icon=":material/delete:", type="secondary", key=f"del_sup_btn_{sel_sup_id}"):
                    delete_supplier_dialog(current_user, sup_data)


# ==============================================================================
# MODAL DIALOGS
# ==============================================================================

@st.dialog("Register New Supplier")
def add_supplier_dialog(curr_user):
    """Modal to register a new wholesale vendor."""
    with st.form("add_supplier_form"):
        st.write("Enter supplier company details:")
        name = st.text_input("Company / Distributor Name *", placeholder="e.g. Cipla Direct Logistics")
        cp = st.text_input("Contact Person", placeholder="e.g. Rajesh Mehta")
        
        c1, c2 = st.columns(2)
        with c1:
            phone = st.text_input("Phone Number *", placeholder="e.g. +91 98765 43210")
            gst = st.text_input("GST / Tax ID", placeholder="e.g. 27ABCDE1234F1Z5")
        with c2:
            email = st.text_input("Email Address", placeholder="e.g. orders@supplier.com")

        addr = st.text_area("Physical Address", placeholder="Warehouse / Office address...")

        submit = st.form_submit_button("Save Supplier Record", type="primary", use_container_width=True)
        if submit:
            try:
                SupplierService.create_supplier(
                    current_user=curr_user,
                    data={
                        "name": name,
                        "contact_person": cp,
                        "phone": phone,
                        "email": email,
                        "address": addr,
                        "gst_number": gst,
                    },
                )
                st.toast(f"Supplier '{name}' registered!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Edit Supplier Profile")
def edit_supplier_dialog(curr_user, sup_obj):
    """Modal to update supplier details."""
    with st.form("edit_supplier_form"):
        st.write(f"Update details for **{sup_obj['name']}**:")
        name = st.text_input("Company / Distributor Name *", value=sup_obj["name"])
        cp = st.text_input("Contact Person", value=sup_obj["contact_person"])

        c1, c2 = st.columns(2)
        with c1:
            phone = st.text_input("Phone Number *", value=sup_obj["phone"])
            gst = st.text_input("GST / Tax ID", value=sup_obj["gst_number"])
        with c2:
            email = st.text_input("Email Address", value=sup_obj["email"])

        addr = st.text_area("Physical Address", value=sup_obj["address"])

        submit = st.form_submit_button("Update Supplier Profile", type="primary", use_container_width=True)
        if submit:
            try:
                SupplierService.update_supplier(
                    current_user=curr_user,
                    supplier_id=sup_obj["id"],
                    data={
                        "name": name,
                        "contact_person": cp,
                        "phone": phone,
                        "email": email,
                        "address": addr,
                        "gst_number": gst,
                    },
                )
                st.toast("Supplier profile updated!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Delete Supplier")
def delete_supplier_dialog(curr_user, sup_obj):
    """Confirmation modal to delete a supplier."""
    st.write(f"Delete vendor **{sup_obj['name']}**?")
    st.caption("Suppliers with existing purchase records cannot be deleted to preserve financial audit history.")

    if st.button("Confirm Delete", type="primary", use_container_width=True):
        try:
            SupplierService.delete_supplier(curr_user, sup_obj["id"])
            st.toast("Supplier removed successfully!", icon="✅")
            st.rerun()
        except ConflictException as ce:
            st.error(ce.message)
        except AppException as e:
            st.error(e.message)
