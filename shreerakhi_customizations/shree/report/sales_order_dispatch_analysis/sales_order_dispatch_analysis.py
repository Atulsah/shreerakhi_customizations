# Copyright (c) 2025, atul and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, nowdate, getdate

CACHE_KEY = "sales_order_allocations"  # cache allocations for 10 minutes

def execute(filters=None):
    filters = filters or {}
    warehouse = filters.get("warehouse")
    customer_filter = filters.get("customer")  # Can be multiple customers
    status = filters.get("status")

    filters_dict = {"status": ["!=", "Cancelled"]}

    # Handle multiple customers (comma-separated)
    customer_list = []
    if customer_filter:
        if isinstance(customer_filter, list):
            customer_list = customer_filter
        else:
            customer_list = [c.strip() for c in customer_filter.split(",") if c.strip()]
        if customer_list:
            filters_dict["customer"] = ["in", customer_list]

    if status:
        filters_dict["status"] = status

    columns = [
        {"label": "Select", "fieldname": "select_box", "fieldtype": "Check", "width": 60},
        {"label": "Sales Order", "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 130},
        {"label": "Customer", "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
        {"label": "City", "fieldname": "city", "fieldtype": "Data", "width": 120},
        {"label": "Pincode", "fieldname": "pincode", "fieldtype": "Data", "width": 100},
        {"label": "% Delivered", "fieldname": "percent_delivered", "fieldtype": "Percent", "width": 120},
        {"label": "% Ready to Dispatch", "fieldname": "percent_ready", "fieldtype": "Percent", "width": 160},
        {"label": "Qty Ready to Dispatch", "fieldname": "qty_ready_to_dispatch", "fieldtype": "Float", "width": 160},
        {"label": "Create Invoice", "fieldname": "invoice_button", "fieldtype": "Button", "width": 150},
    ]

    # Step 1: Build stock map
    stock_map = {}
    if warehouse:
        bins = frappe.db.get_all("Bin", filters={"warehouse": warehouse}, fields=["item_code", "actual_qty"])
        for b in bins:
            stock_map[b.item_code] = flt(b.actual_qty)

    # Step 2: Fetch Sales Orders FIFO
    sales_orders = frappe.get_all(
        "Sales Order",
        filters=filters_dict,
        fields=["name", "customer", "customer_name", "transaction_date"],
        order_by="transaction_date asc, name asc",
    )

    data = []
    allocation_data = {}

    for so in sales_orders:
        so_doc = frappe.get_doc("Sales Order", so.name)

        total_qty = 0
        delivered_qty = 0
        ready_qty = 0
        allocation_data[so.name] = {}
        all_items_delivered = True

        for item in so_doc.items:
            ordered = flt(item.qty)
            delivered = flt(item.delivered_qty)

            if delivered >= ordered:
                continue

            all_items_delivered = False
            pending = max(ordered - delivered, 0)

            available_stock = stock_map.get(item.item_code, 0)
            allocatable = min(pending, available_stock)

            # Deduct allocated from stock
            stock_map[item.item_code] = available_stock - allocatable

            total_qty += ordered
            delivered_qty += delivered
            ready_qty += allocatable

            allocation_data[so.name][item.item_code] = allocatable

        # Skip fully delivered orders
        if all_items_delivered:
            allocation_data.pop(so.name, None)
            continue

        percent_delivered = round((delivered_qty / total_qty) * 100, 2) if total_qty else 0
        percent_ready = round((ready_qty / total_qty) * 100, 2) if total_qty else 0

        # Customer address
        city = ""
        pincode = ""
        addr = frappe.db.get_value(
            "Dynamic Link",
            {"link_doctype": "Customer", "link_name": so_doc.customer},
            "parent",
        )
        if addr:
            city = frappe.db.get_value("Address", addr, "city") or ""
            pincode = frappe.db.get_value("Address", addr, "pincode") or ""

        data.append(
            {
                "select_box": 0,
                "sales_order": so.name,
                "customer_name": so.customer_name,
                "city": city,
                "pincode": pincode,
                "percent_delivered": percent_delivered,
                "percent_ready": percent_ready,
                "qty_ready_to_dispatch": ready_qty,
                "invoice_button": "Create Invoice",
            }
        )

    frappe.cache().set_value(CACHE_KEY, allocation_data, expires_in_sec=600)
    return columns, data


@frappe.whitelist()
def create_sales_invoice(sales_order, warehouse=None):
    allocations = frappe.cache().get_value(CACHE_KEY) or {}
    so_alloc = allocations.get(sales_order, {})

    if not so_alloc:
        frappe.throw(f"No stock allocated for Sales Order {sales_order}")

    so_doc = frappe.get_doc("Sales Order", sales_order)
    inv = frappe.new_doc("Sales Invoice")
    inv.customer = so_doc.customer
    inv.sales_order = so_doc.name
    inv.posting_date = nowdate()

    # --- Updated: ensure due_date >= posting_date ---
    so_date = getdate(so_doc.transaction_date)
    posting_date = getdate(inv.posting_date)
    if so_doc.payment_terms_template:
        inv.payment_terms_template = so_doc.payment_terms_template
        inv.due_date = so_doc.get_payment_due_date() or posting_date
    else:
        inv.due_date = max(so_date, posting_date)
    # ----------------------------------------------

    for item in so_doc.items:
        alloc_qty = flt(so_alloc.get(item.item_code, 0))
        if alloc_qty > 0:
            inv.append(
                "items",
                {
                    "item_code": item.item_code,
                    "qty": alloc_qty,
                    "uom": item.uom,
                    "rate": item.rate,
                    "cost_center": item.get("cost_center"),
                    "warehouse": warehouse or item.warehouse,
                    "so_detail": item.name,
                    "sales_order": so_doc.name,
                },
            )

    if not inv.items:
        frappe.throw("No items available to invoice for this order based on current stock allocation.")

    inv.insert(ignore_permissions=True)
    inv.save()
    frappe.db.commit()
    return {"name": inv.name}


@frappe.whitelist()
def bulk_create_invoices(sales_orders, warehouse=None):
    import json

    try:
        so_list = json.loads(sales_orders)
    except Exception:
        frappe.throw("Invalid JSON format for sales_orders")

    allocations = frappe.cache().get_value(CACHE_KEY) or {}
    created = []

    for so_name in so_list:
        so_alloc = allocations.get(so_name, {})
        if not so_alloc:
            continue

        try:
            so_doc = frappe.get_doc("Sales Order", so_name)
            inv = frappe.new_doc("Sales Invoice")
            inv.customer = so_doc.customer
            inv.sales_order = so_doc.name
            inv.posting_date = nowdate()

            # --- Updated: ensure due_date >= posting_date ---
            so_date = getdate(so_doc.transaction_date)
            posting_date = getdate(inv.posting_date)
            if so_doc.payment_terms_template:
                inv.payment_terms_template = so_doc.payment_terms_template
                inv.due_date = so_doc.get_payment_due_date() or posting_date
            else:
                inv.due_date = max(so_date, posting_date)
            # ----------------------------------------------

            for item in so_doc.items:
                alloc_qty = flt(so_alloc.get(item.item_code, 0))
                if alloc_qty > 0:
                    inv.append(
                        "items",
                        {
                            "item_code": item.item_code,
                            "qty": alloc_qty,
                            "uom": item.uom,
                            "rate": item.rate,
                            "cost_center": item.get("cost_center"),
                            "warehouse": warehouse or item.warehouse,
                            "so_detail": item.name,
                            "sales_order": so_doc.name,
                        },
                    )

            if not inv.items:
                continue

            inv.insert(ignore_permissions=True)
            inv.save()
            created.append(inv.name)

        except Exception as e:
            frappe.log_error(f"Failed to create invoice for {so_name}: {str(e)}")

    frappe.db.commit()
    return created