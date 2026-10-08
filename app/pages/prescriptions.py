"""Medical Prescriptions and Schedule H compliance registry page."""

from datetime import date
from typing import Dict, Any
import streamlit as st
import pandas as pd

from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.services.prescription_service import PrescriptionService
from app.services.customer_service import CustomerService
from app.core.exceptions import AppException, ConflictException

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/prescriptions: Medical Prescriptions Registry")
st.caption("Track doctor prescriptions, verify Medical Council registration numbers, and ensure Schedule H/X statutory dispensing compliance")

all_prescriptions = PrescriptionService.list_prescriptions()
total_rx = len(all_prescriptions)
dispensed_rx_count = sum(1 for rx in all_prescriptions if rx["sales_count"] > 0)

k1, k2 = st.columns(2)
with k1:
    render_metric_card("Registered Prescriptions", str(total_rx), "Statutory medical records", accent="teal", icon="📋")
with k2:
    render_metric_card("Dispensed Invoices Linked", str(dispensed_rx_count), "Counter sales with attached Rx", accent="blue", icon="💊")

st.markdown("---")

c_btn, _, c_search = st.columns([2, 1, 3])
with c_btn:
    if st.button("Log New Prescription", icon=":material/note_add:", type="primary", use_container_width=True):
        add_prescription_dialog(current_user)

with c_search:
    search_kw = st.text_input("Search prescriptions", placeholder="Search by patient, doctor, reg no...", label_visibility="collapsed")

prescriptions = PrescriptionService.list_prescriptions(search=search_kw)

if not prescriptions:
    render_empty_state("No Prescriptions Found", "No prescription records match your search.")
else:
    rx_table = []
    for rx in prescriptions:
        rx_table.append({
            "Rx ID": rx["id"],
            "Patient Name": rx["patient_name"],
            "Age / Gender": f"{rx['patient_age'] or '-'} / {rx['patient_gender']}",
            "Prescribing Doctor": rx["doctor_name"],
            "Doctor Reg No": rx["doctor_reg_no"],
            "Prescription Date": rx["prescription_date"],
            "Diagnosis": rx["diagnosis"],
            "Linked Sales": f"{rx['sales_count']} sales",
        })

    st.dataframe(pd.DataFrame(rx_table), use_container_width=True, hide_index=True)

    st.markdown("### Prescription Inspection & Clinical Notes")
    rx_choices = {f"Rx #{rx['id']} - {rx['patient_name']} (Dr. {rx['doctor_name']})": rx["id"] for rx in prescriptions}
    sel_rx_label = st.selectbox("Select prescription to view:", options=list(rx_choices.keys()))
    sel_rx_id = rx_choices[sel_rx_label]

    if sel_rx_id:
        rx_detail = PrescriptionService.get_prescription(sel_rx_id)
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"#### Patient: {rx_detail['patient_name']}")
                st.caption(f"Age: **{rx_detail['patient_age'] or 'N/A'}** | Gender: **{rx_detail['patient_gender'] or 'N/A'}**")
                st.write(f"🩺 Doctor: **{rx_detail['doctor_name']}**")
                st.write(f"📜 Medical Council Reg: **`{rx_detail['doctor_reg_no'] or 'N/A'}`**")
            with col2:
                st.write(f"📅 Date: **{rx_detail['prescription_date']}**")
                st.write(f"🔍 Clinical Diagnosis: **{rx_detail['diagnosis'] or 'None recorded'}**")
                st.write(f"📝 Doctor's Dosage Notes: **{rx_detail['notes'] or 'None recorded'}**")

            st.markdown("##### Sales Billed Under This Prescription:")
            if not rx_detail["sales"]:
                st.info("No sales billed against this prescription yet.")
            else:
                st.dataframe(pd.DataFrame(rx_detail["sales"]), use_container_width=True, hide_index=True)

            col_act1, col_act2, _ = st.columns([1.5, 1.5, 3])
            with col_act1:
                if st.button("Edit Prescription", icon=":material/edit:", key=f"edit_rx_{sel_rx_id}"):
                    edit_prescription_dialog(current_user, rx_detail)
            with col_act2:
                if st.button("Delete Prescription", icon=":material/delete:", type="secondary", key=f"del_rx_{sel_rx_id}"):
                    delete_prescription_dialog(current_user, rx_detail)


# ==============================================================================
# MODAL DIALOGS
# ==============================================================================

@st.dialog("Log Doctor Prescription")
def add_prescription_dialog(curr_user):
    """Modal to create a new medical prescription."""
    customers = CustomerService.list_customers()
    cust_options = {"None (Unregistered Patient)": None}
    for c in customers:
        cust_options[f"{c['name']} (Phone: {c['phone']})"] = c["id"]

    with st.form("add_rx_form"):
        st.write("Enter prescription compliance details:")
        c_sel = st.selectbox("Link to Customer Profile (Optional)", options=list(cust_options.keys()))
        selected_cust_id = cust_options[c_sel]

        c1, c2 = st.columns(2)
        with c1:
            p_name = st.text_input("Patient Full Name *", placeholder="e.g. Rajesh Sharma")
            p_age = st.number_input("Patient Age", min_value=1, max_value=120, value=35)
        with c2:
            p_gender = st.selectbox("Gender", options=["Male", "Female", "Other"])
            rx_date = st.date_input("Prescription Date *", value=date.today())

        c3, c4 = st.columns(2)
        with c3:
            doc_name = st.text_input("Doctor Name *", placeholder="e.g. Dr. Sneha Roy, MD")
        with c4:
            doc_reg = st.text_input("Medical Council Reg. No", placeholder="e.g. MCI-88492-A")

        diag = st.text_input("Clinical Diagnosis / Condition", placeholder="e.g. Acute Bronchitis")
        notes = st.text_area("Doctor Instructions & Dosage Regimen", placeholder="e.g. Amoxicillin 500mg TDS for 5 days after food")

        submit = st.form_submit_button("Save Prescription", type="primary", use_container_width=True)
        if submit:
            try:
                PrescriptionService.create_prescription(
                    current_user=curr_user,
                    data={
                        "customer_id": selected_cust_id,
                        "patient_name": p_name,
                        "patient_age": int(p_age),
                        "patient_gender": p_gender,
                        "prescription_date": rx_date,
                        "doctor_name": doc_name,
                        "doctor_reg_no": doc_reg,
                        "diagnosis": diag,
                        "notes": notes,
                    },
                )
                st.toast("Prescription logged successfully!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Edit Prescription")
def edit_prescription_dialog(curr_user, rx_data):
    """Modal to update prescription."""
    with st.form("edit_rx_form"):
        st.write(f"Edit Prescription for **{rx_data['patient_name']}**:")
        c1, c2 = st.columns(2)
        with c1:
            p_name = st.text_input("Patient Name *", value=rx_data["patient_name"])
            p_age = st.number_input("Age", min_value=1, max_value=120, value=int(rx_data["patient_age"] or 30))
        with c2:
            p_gender = st.selectbox("Gender", options=["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(rx_data["patient_gender"]) if rx_data["patient_gender"] in ["Male", "Female", "Other"] else 0)
            rx_date = st.date_input("Prescription Date *", value=rx_data["prescription_date"])

        c3, c4 = st.columns(2)
        with c3:
            doc_name = st.text_input("Doctor Name *", value=rx_data["doctor_name"])
        with c4:
            doc_reg = st.text_input("Reg No", value=rx_data["doctor_reg_no"] or "")

        diag = st.text_input("Diagnosis", value=rx_data["diagnosis"] or "")
        notes = st.text_area("Instructions", value=rx_data["notes"] or "")

        submit = st.form_submit_button("Update Prescription", type="primary", use_container_width=True)
        if submit:
            try:
                PrescriptionService.update_prescription(
                    current_user=curr_user,
                    prescription_id=rx_data["id"],
                    data={
                        "patient_name": p_name,
                        "patient_age": int(p_age),
                        "patient_gender": p_gender,
                        "prescription_date": rx_date,
                        "doctor_name": doc_name,
                        "doctor_reg_no": doc_reg,
                        "diagnosis": diag,
                        "notes": notes,
                        "customer_id": rx_data["customer_id"],
                    },
                )
                st.toast("Prescription updated!", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)


@st.dialog("Delete Prescription")
def delete_prescription_dialog(curr_user, rx_data):
    """Confirmation modal to delete a prescription."""
    st.write(f"Delete prescription from **{rx_data['doctor_name']}** for **{rx_data['patient_name']}**?")
    st.caption("Prescriptions with attached dispensing records cannot be deleted.")

    if st.button("Confirm Delete", type="primary", use_container_width=True):
        try:
            PrescriptionService.delete_prescription(curr_user, rx_data["id"])
            st.toast("Prescription deleted.", icon="✅")
            st.rerun()
        except ConflictException as ce:
            st.error(ce.message)
        except AppException as e:
            st.error(e.message)
