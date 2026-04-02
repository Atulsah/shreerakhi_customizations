# Copyright (c) 2025, atul and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_data(filters):
    conditions, values = get_item_conditions(filters)
    values.update({
        'from_date': filters.from_date,
        'to_date': filters.to_date,
    })

    return frappe.db.sql("""
        SELECT
            si.name,
            si.customer,
            si.customer_name,
            si.place_of_supply,
            si.total_qty,
            si.custom_number_of_carton,
            si.base_total,
            si.additional_discount_percentage,
            si.discount_amount,
            si.rounded_total,
            si.custom_bos_transporter
        FROM
            `tabSales Invoice` si
        WHERE
            si.posting_date BETWEEN %(from_date)s AND %(to_date)s
            {conditions}
        ORDER BY
            si.name ASC
    """.format(conditions=conditions), values, as_dict=1)


def get_item_conditions(filters):
    conditions = []
    values = {}

    # Document Status filter
    # Agar koi status select na kiya ho to draft + submitted + cancelled sab aayenge
    docstatus_map = {
        "Draft": 0,
        "Submitted": 1,
        "Cancelled": 2,
    }

    selected_status = filters.get("docstatus")
    if selected_status and selected_status in docstatus_map:
        conditions.append("si.docstatus = %(docstatus)s")
        values["docstatus"] = docstatus_map[selected_status]
    else:
        # Koi filter nahi diya — saare invoices dikhao (0, 1, 2)
        conditions.append("si.docstatus IN (0, 1, 2)")

    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
        values["customer"] = filters.customer

    if filters.get("company"):
        conditions.append("si.company = %(company)s")
        values["company"] = filters.company

    if filters.get("warehouse"):
        conditions.append("""
            EXISTS (
                SELECT 1 FROM `tabSales Invoice Item` sii
                WHERE sii.parent = si.name
                AND sii.warehouse = %(warehouse)s
            )
        """)
        values["warehouse"] = filters.warehouse

    if filters.get("brand"):
        conditions.append("""
            EXISTS (
                SELECT 1 FROM `tabSales Invoice Item` sii
                WHERE sii.parent = si.name
                AND sii.brand = %(brand)s
            )
        """)
        values["brand"] = filters.brand

    if filters.get("item_group"):
        conditions.append("""
            EXISTS (
                SELECT 1 FROM `tabSales Invoice Item` sii
                WHERE sii.parent = si.name
                AND sii.item_group = %(item_group)s
            )
        """)
        values["item_group"] = filters.item_group

    condition_str = "AND " + " AND ".join(conditions) if conditions else ""
    return condition_str, values


def get_columns():
    return [
        {
            "fieldname": "name",
            "label": _("Invoice No"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 150
        },
        {
            "fieldname": "customer",
            "label": _("Customer ID"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 120
        },
        {
            "fieldname": "customer_name",
            "label": _("Customer Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "place_of_supply",
            "label": _("Place"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "total_qty",
            "label": _("Quantity"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            # "Cases" ki jagah "Total Number of Carton"
            "fieldname": "custom_number_of_carton",
            "label": _("Total Number of Carton"),
            "fieldtype": "Float",
            "width": 160
        },
        {
            "fieldname": "base_total",
            "label": _("Gross Amount"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "additional_discount_percentage",
            "label": _("Discount %"),
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "fieldname": "discount_amount",
            "label": _("Discount"),
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "fieldname": "rounded_total",
            "label": _("Net Amount"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "custom_bos_transporter",
            "label": _("Transport"),
            "fieldtype": "Data",
            "width": 150
        },
    ]