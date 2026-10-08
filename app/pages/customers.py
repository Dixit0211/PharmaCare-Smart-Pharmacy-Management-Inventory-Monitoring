"""Patient and customer directory management page."""

from typing import Dict, Any
import streamlit as st
import pandas as pd

from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.services.customer_service import CustomerService
from app.core.exceptions import AppException, ConflictException

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/group: Patient & Customer Directory")
st.caption("Manage patient profiles, contact records, recurring prescriptions, and sales history")

all_customers = CustomerService.list_customers()
total_customers = len(all_customers)
total_dispensed_sales = sum(c["sale_count"] for c in all_customers)
total_revenue = sum(c["total_spent"] for c in all_customers)

k1, k2, k3 = st.columns(3)
with k1:
    render_metric_card("Registered Patients", str(total_customers), "Active customer records", accent="teal", icon="👥")
with k2:
    render_metric_card("Completed Invoices", str(total_dispensed_sales), "Prescription & OTC billings", accent="blue", icon="🧾")
with k3:
    render_metric_card("Customer Revenue", f"₹{total_revenue:,.2f}", "Total lifetime purchases", accent="green", icon="💰")

st.markdown("---")

c_btn, _, c_search = st.columns([2, 1, 3])
with c_btn:
    if st.button("Add New Patient / Customer", icon=":material/person_add:", type="primary", use_container_width=True):
        add_customer_dialog(current_user)

with c_search:
    search_q = st.text_input("Search directory", placeholder="Search by name, phone, email...", label_visibility="collapsed")

customers = CustomerService.list_customers(search=search_q)

if not customers:
    render_empty_state("No Customers Found", "No patient records match the search query.")
else:
    c_table = []
    for c in customers:
        c_table.append({
            "Customer ID": c["id"],
            "Patient / Customer Name": c["name"],
            "Phone Number": c["phone"],
            "Email Address": c["email"],
            "Address": c["address"],
            "Prescriptions": f"{c['rx_count']} Rx",
            "Invoices": f"{c['sale_count']} sales",
            "Total Spent": f"₹{c['total_spent']:,.2f}",
        })

    st.dataframe(pd.DataFrame(c_table), use_container_width=True, hide_index=True)

    st.markdown("### Patient Profile & History Inspection")
    cust_choices = {f"{c['name']} (Phone: {c['phone']}) - Spent: ₹{c['total_spent']:,.2f}": c["id"] for c in customers}
    sel_c_label = st.selectbox("Select patient to view history:", options=list(cust_choices.keys()))
    sel_c_id = cust_choices[sel_c_label]

    if sel_c_id:
        c_detail = CustomerService.get_customer(sel_c_id)
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"#### {c_detail['name']}")
                st.write(f"📞 Phone: **{c_detail['phone']}**")
                st.write(f"✉️ Email: **{c_detail['email'] or 'N/A'}**")
            with col2:
                st.write(f"📍 Address: **{c_detail['address'] or 'N/A'}**")
                st.write(f"💰 Total Billed: **₹{c_detail['total_spent']:,.2f}**")

            st.markdown("##### Past Sales Invoices:")
            if not c_detail["sales"]:
                st.info("No sales transactions recorded for this patient.")
            else:
                sales_df = pd.DataFrame(c_detail["sales"])
                st.dataframe(sales_df, use_container_width=True, hide_index=True)

            col_act1, col_act2, _ = st.columns([1.5, 1.5, 3])
            with col_act1:
                if st.button("Edit Patient Info", icon=":material/edit:", key=f"edit_cust_btn_{sel_c_id}"):
                    edit_customer_dialog(current_user, c_detail)
            with col_act2:
                if st.button("Delete Customer", icon=":material/delete:", type="secondary", key=f"del_cust_btn_{sel_c_id}"):
                    delete_customer_dialog(current_user, c_detail)


# ==============================================================================
# MODAL DIALOGS
# ==============================================================================

@st.dialog("Register New Patient / Customer")
def add_customer_dialog(curr_user):
    """Modal to register a new customer."""
    with st.form("add_customer_form"):
        st.write("Enter patient contact information:")
        name = st.text_input("Full Name *", placeholder="e.g. Ramesh Sharma")
        c1, c2 = st.columns(2)
        with c1:
            phone = st.text_input("Phone Number *", placeholder="e.g. +91 98765 43210")
        with c2:
            email = st.text_input("Email Address", placeholder="e.g. ramesh@example.com")

        addr = st.text_area("Residential Address", placeholder="Apartment, Street, City...")

        submit = st.form_submit_button("Save Customer Record", type="primary", use_container_width=True)
        if submit:
            try:
                CustomerService.create_customer(
                    current_user=curr_user,
                    data={"name": name, "phone": phone, "email": email, "address": addr},
                )
                st.toast(f"Patient profile '{name}' created!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Edit Patient Profile")
def edit_customer_dialog(curr_user, cust_data):
    """Modal to edit customer profile."""
    with st.form("edit_customer_form"):
        st.write(f"Edit details for **{cust_data['name']}**:")
        name = st.text_input("Full Name *", value=cust_data["name"])
        c1, c2 = st.columns(2)
        with c1:
            phone = st.text_input("Phone Number *", value=cust_data["phone"])
        with c2:
            email = st.text_input("Email Address", value=cust_data["email"])

        addr = st.text_area("Residential Address", value=cust_data["address"])

        submit = st.form_submit_button("Update Profile", type="primary", use_container_width=True)
        if submit:
            try:
                CustomerService.update_customer(
                    current_user=curr_user,
                    customer_id=cust_data["id"],
                    data={"name": name, "phone": phone, "email": email, "address": addr},
                )
                st.toast("Profile updated successfully!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Delete Customer Profile")
def delete_customer_dialog(curr_user, cust_data):
    """Confirmation modal to delete a customer."""
    st.write(f"Delete record for **{cust_data['name']}**?")
    st.caption("Patients with existing billing records cannot be deleted to preserve financial audit history.")

    if st.button("Confirm Delete", type="primary", use_container_width=True):
        try:
            CustomerService.delete_customer(curr_user, cust_data["id"])
            st.toast("Customer deleted.", icon="✅")
            st.rerun()
        except ConflictException as ce:
            st.error(ce.message)
        except AppException as e:
            st.error(e.message)
