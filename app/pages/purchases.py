"""Inward stock purchase orders and procurement intake page."""

from datetime import date, timedelta
from typing import Dict, Any, List
import streamlit as st
import pandas as pd

from app.utils.session import is_authenticated, get_current_user
from app.components.styles import inject_custom_styles
from app.components.sidebar import render_sidebar
from app.components.metric_card import render_metric_card
from app.components.empty_state import render_empty_state
from app.components.status_badge import render_status_badge
from app.services.purchase_service import PurchaseService
from app.services.supplier_service import SupplierService
from app.services.medicine_service import MedicineService
from app.core.exceptions import AppException

if not is_authenticated():
    st.warning("Please log in to access the system.")
    st.stop()

inject_custom_styles()
render_sidebar()

current_user = get_current_user()

st.markdown("## :material/inventory_2: Inward Stock Purchases & Procurement")
st.caption("Record supplier procurement invoices, add line items with batch numbers & expiry dates, and auto-update inventory")

# Initialize procurement cart in session state
if "purchase_items_cart" not in st.session_state:
    st.session_state["purchase_items_cart"] = []

all_purchases = PurchaseService.list_purchases()
total_inv_count = len(all_purchases)
total_procurement_cost = sum(p["total_amount"] for p in all_purchases if p["status"] == "received")
active_suppliers_count = len(SupplierService.list_suppliers())

# KPI Metric Cards
k1, k2, k3 = st.columns(3)
with k1:
    render_metric_card("Total Inward Invoices", str(total_inv_count), "Received stock vouchers", accent="teal", icon="📑")
with k2:
    render_metric_card("Total Spend", f"₹{total_procurement_cost:,.2f}", "Received procurement volume", accent="green", icon="💰")
with k3:
    render_metric_card("Registered Suppliers", str(active_suppliers_count), "Wholesale supply partners", accent="blue", icon="🏢")

st.markdown("---")

tab_new_order, tab_history = st.tabs([
    ":material/add_shopping_cart: Inward Stock Entry (New Invoice)",
    f":material/receipt_long: Purchase History ({total_inv_count})",
])

# ==============================================================================
# TAB 1: INWARD STOCK INTAKE (NEW PURCHASE)
# ==============================================================================
with tab_new_order:
    st.markdown("### 📥 Record Inward Supplier Invoice")
    st.caption("Incoming batches added here are automatically registered and reflected in sellable stock (FEFO).")

    suppliers = SupplierService.list_suppliers()
    medicines = MedicineService.list_medicines()

    if not suppliers:
        st.error("Please add at least one Supplier in the 'Suppliers' section before recording purchases.")
    elif not medicines:
        st.error("Please add medicines in the 'Medicines Catalog' before recording purchases.")
    else:
        sup_map = {f"{s['name']} (Phone: {s['phone']})": s["id"] for s in suppliers}
        med_map = {f"{m['name']} ({m['strength']}) - {m['category_name']}": m for m in medicines}

        # Step 1: Invoice Header
        with st.container(border=True):
            st.markdown("##### 1. Invoice Header Details")
            h1, h2, h3 = st.columns(3)
            with h1:
                selected_sup_label = st.selectbox("Wholesale Supplier *", options=list(sup_map.keys()), key="p_sup_select")
                selected_sup_id = sup_map[selected_sup_label]
            with h2:
                inv_no_input = st.text_input("Supplier Invoice No *", placeholder="e.g. PUR-2026-904", key="p_inv_no").upper()
            with h3:
                p_date_input = st.date_input("Invoice Date *", value=date.today(), key="p_date")

            p_notes_input = st.text_input("Procurement Notes / PO Reference", placeholder="e.g. Monthly replenishment batch #10", key="p_notes")

        # Step 2: Line Items Builder
        with st.container(border=True):
            st.markdown("##### 2. Add Line Items to Invoice")
            l1, l2, l3 = st.columns([2, 1.5, 1.5])
            with l1:
                sel_med_label = st.selectbox("Select Medicine *", options=list(med_map.keys()), key="p_item_med")
                sel_med_obj = med_map[sel_med_label]
            with l2:
                batch_no_input = st.text_input("Batch Number *", placeholder="e.g. PARA-2024-B4", key="p_item_batch").upper()
            with l3:
                expiry_date_input = st.date_input("Expiry Date *", value=date.today() + timedelta(days=365), key="p_item_exp")

            l4, l5, l6 = st.columns([1.5, 1.5, 2])
            with l4:
                item_qty = st.number_input("Received Quantity (Units) *", min_value=1, value=100, step=10, key="p_item_qty")
            with l5:
                # Default purchase price to 65% of selling price or custom
                default_p_price = round(sel_med_obj["selling_price"] * 0.65, 2)
                item_price = st.number_input("Unit Purchase Price (₹) *", min_value=0.0, value=float(default_p_price), step=1.0, key="p_item_price")
            with l6:
                line_total = round(item_qty * item_price, 2)
                st.write("")
                st.markdown(f"**Subtotal: ₹{line_total:,.2f}**")

            if st.button("➕ Add Item to Invoice", type="secondary"):
                if not batch_no_input:
                    st.error("Batch number is required.")
                elif expiry_date_input < date.today():
                    st.error("Expiry date cannot be in the past.")
                else:
                    st.session_state["purchase_items_cart"].append({
                        "medicine_id": sel_med_obj["id"],
                        "medicine_name": sel_med_obj["name"],
                        "strength": sel_med_obj["strength"],
                        "batch_no": batch_no_input,
                        "expiry_date": expiry_date_input.strftime("%Y-%m-%d"),
                        "quantity": int(item_qty),
                        "purchase_price": float(item_price),
                        "subtotal": line_total,
                    })
                    st.toast(f"Added {sel_med_obj['name']} (Batch {batch_no_input})", icon="✅")
                    st.rerun()

        # Step 3: Current Cart & Submission
        cart = st.session_state["purchase_items_cart"]
        if cart:
            st.markdown("##### 3. Line Items in Current Invoice:")
            cart_df_rows = []
            invoice_grand_total = 0.0
            for idx, c_it in enumerate(cart):
                invoice_grand_total += c_it["subtotal"]
                cart_df_rows.append({
                    "#": idx + 1,
                    "Medicine": f"{c_it['medicine_name']} ({c_it['strength']})",
                    "Batch No": c_it["batch_no"],
                    "Expiry Date": c_it["expiry_date"],
                    "Quantity": f"{c_it['quantity']} units",
                    "Purchase Price": f"₹{c_it['purchase_price']:.2f}",
                    "Subtotal": f"₹{c_it['subtotal']:,.2f}",
                })

            st.dataframe(pd.DataFrame(cart_df_rows), use_container_width=True, hide_index=True)

            sub_c1, sub_c2, sub_c3 = st.columns([2, 2, 2])
            with sub_c1:
                st.markdown(f"### Grand Total: **₹{invoice_grand_total:,.2f}**")
            with sub_c2:
                if st.button("Clear Line Items", icon=":material/clear_all:", type="secondary"):
                    st.session_state["purchase_items_cart"] = []
                    st.rerun()
            with sub_c3:
                if st.button("Submit Inward Invoice", icon=":material/check_circle:", type="primary", use_container_width=True):
                    if not inv_no_input:
                        st.error("Please provide the Supplier Invoice Number.")
                    else:
                        try:
                            res = PurchaseService.create_purchase_order(
                                current_user=current_user,
                                supplier_id=selected_sup_id,
                                invoice_no=inv_no_input,
                                purchase_date_val=p_date_input,
                                items=cart,
                                notes=p_notes_input,
                            )
                            st.session_state["purchase_items_cart"] = []
                            st.toast(f"Purchase invoice '{res['invoice_no']}' recorded and stock updated!", icon="🎉")
                            st.rerun()
                        except AppException as e:
                            st.error(e.message)


# ==============================================================================
# TAB 2: PURCHASE INVOICES & HISTORY
# ==============================================================================
with tab_history:
    st.markdown("### 🧾 Inward Procurement Invoices Registry")

    h_f1, h_f2, h_f3 = st.columns([2, 2, 2])
    with h_f1:
        search_kw = st.text_input("Search Invoices", placeholder="Filter by invoice # or supplier...", key="p_hist_search")
    with h_f2:
        status_filter = st.selectbox("Filter Status", options=["All", "Received", "Cancelled"], key="p_hist_status")
    with h_f3:
        pass

    purchases_list = PurchaseService.list_purchases(
        status=status_filter,
        search=search_kw,
    )

    if not purchases_list:
        render_empty_state("No Purchase Invoices", "No invoices match the selected filters.")
    else:
        p_table = []
        for p in purchases_list:
            p_table.append({
                "Invoice No": p["invoice_no"],
                "Supplier": p["supplier_name"],
                "Date": p["purchase_date"],
                "Items Count": f"{p['item_count']} items",
                "Total Amount": f"₹{p['total_amount']:,.2f}",
                "Status": p["status"].capitalize(),
                "Notes": p["notes"],
            })

        st.dataframe(pd.DataFrame(p_table), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Invoice Inspection & Line Items Breakdown")
        p_choices = {f"{p['invoice_no']} ({p['supplier_name']}) - ₹{p['total_amount']:,.2f}": p["id"] for p in purchases_list}
        sel_p_label = st.selectbox("Select purchase invoice to inspect:", options=list(p_choices.keys()), key="p_inspect_select")
        sel_p_id = p_choices[sel_p_label]

        if sel_p_id:
            p_detail = PurchaseService.get_purchase(sel_p_id)
            with st.container(border=True):
                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    st.markdown(f"#### Invoice: {p_detail['invoice_no']}")
                    st.caption(f"Supplier: **{p_detail['supplier_name']}** (GST: `{p_detail['supplier_gst']}`)")
                    st.write(f"📞 Contact Phone: **{p_detail['supplier_phone']}**")
                with c_d2:
                    st.write(f"📅 Inward Date: **{p_detail['purchase_date']}**")
                    st.write(f"💰 Grand Total: **₹{p_detail['total_amount']:,.2f}**")
                    render_status_badge(p_detail["status"])

                st.markdown("##### Line Items in this Invoice:")
                items_table = []
                for it in p_detail["items"]:
                    items_table.append({
                        "Medicine": it["medicine_name"],
                        "Batch No": it["batch_no"],
                        "Expiry Date": it["expiry_date"],
                        "Quantity Received": f"{it['quantity']} units",
                        "Unit Cost": f"₹{it['purchase_price']:.2f}",
                        "Subtotal": f"₹{it['subtotal']:,.2f}",
                    })
                st.dataframe(pd.DataFrame(items_table), use_container_width=True, hide_index=True)

                if p_detail["status"] == "received":
                    if st.button("Cancel Invoice & Reverse Stock", icon=":material/cancel:", type="secondary"):
                        cancel_purchase_dialog(current_user, p_detail)


# ==============================================================================
# MODAL DIALOGS
# ==============================================================================

@st.dialog("Cancel Purchase Order")
def cancel_purchase_dialog(curr_user, p_obj):
    """Modal to cancel a purchase invoice and reverse added stock."""
    st.warning(f"Are you sure you want to cancel invoice **{p_obj['invoice_no']}**?")
    st.caption("This will subtract the received quantities from active batch stock. If any units have already been sold, cancellation is blocked.")

    reason = st.text_input("Mandatory Cancellation Reason *", placeholder="e.g. Duplicate entry / Goods returned to supplier")

    if st.button("Confirm Cancellation", type="primary", use_container_width=True):
        if not reason:
            st.error("Please provide a cancellation reason.")
        else:
            try:
                PurchaseService.cancel_purchase_order(curr_user, p_obj["id"], reason)
                st.toast(f"Invoice '{p_obj['invoice_no']}' cancelled and stock reversed.", icon="✅")
                st.rerun()
            except AppException as e:
                st.error(e.message)
