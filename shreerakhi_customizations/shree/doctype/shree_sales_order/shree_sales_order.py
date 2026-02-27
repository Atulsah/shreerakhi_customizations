# Copyright (c) 2026, atul and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class ShreeSalesOrder(Document):

    # ──────────────────────────────────────────────
    #  Hooks
    # ──────────────────────────────────────────────

    def before_insert(self):
        """Portal user se customer auto-set karo"""
        if not self.customer:
            customer = _get_customer_for_user(frappe.session.user)
            if customer:
                self.customer = customer
        self._load_customer_details()

    def validate(self):
        self._set_item_amounts()
        self._calculate_totals()
        self._validate_items()

    def on_submit(self):
        """
        Customer submit kare to:
        1. Shree Sales Order → status = Submitted
        2. ERPNext standard Sales Order (Draft) auto-create
        """
        self.db_set("status", "Submitted")
        self._create_erpnext_sales_order()

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    # ──────────────────────────────────────────────
    #  Create ERPNext Standard Sales Order (Draft)
    # ──────────────────────────────────────────────

    def _create_erpnext_sales_order(self):
        try:
            # Price list
            price_list = (
                frappe.db.get_value("Customer", self.customer, "default_price_list")
                or frappe.db.get_single_value("Selling Settings", "selling_price_list")
                or "Standard Selling"
            )

            # Default warehouse
            default_warehouse = (
                frappe.db.get_single_value("Stock Settings", "default_warehouse") or ""
            )

            # Build items
            so_items = []
            for row in self.items:
                if not frappe.db.exists("Item", row.item_code):
                    frappe.log_error(
                        f"Item {row.item_code} not found — {self.name}",
                        "Shree Sales Order"
                    )
                    continue

                so_items.append({
                    "item_code":     row.item_code,
                    "item_name":     row.item_name,
                    "qty":           flt(row.qty),
                    "uom":           row.uom,
                    "rate":          flt(row.rate),
                    "amount":        flt(row.amount),
                    "warehouse":     default_warehouse,
                    "delivery_date": today(),
                    "description":   row.item_name or row.item_code,
                })

            if not so_items:
                frappe.throw("Koi valid item nahi mila Sales Order banane ke liye.")

            # Create Sales Order
            so = frappe.new_doc("Sales Order")
            so.customer              = self.customer
            so.company               = self.company
            so.transaction_date      = self.transaction_date or today()
            so.delivery_date         = today()
            so.selling_price_list    = price_list
            so.currency              = (
                self.currency
                or frappe.db.get_value("Company", self.company, "default_currency")
            )
            so.customer_address      = self.customer_address
            so.address_display       = self.address_display
            so.shipping_address_name = self.shipping_address_name
            so.shipping_address      = self.shipping_address
            so.order_type            = "Sales"
            # Reference back to Shree Sales Order
            so.po_no   = self.name
            so.po_date = self.transaction_date

            for item_row in so_items:
                so.append("items", item_row)

            so.flags.ignore_permissions = True
            so.insert()  # Insert as Draft only — do NOT submit

            # Save ERPNext SO reference on this doc
            self.db_set("erpnext_sales_order", so.name)

            frappe.msgprint(
                f"✅ Sales Order <b><a href='/app/sales-order/{so.name}'>{so.name}</a></b> "
                f"Draft mein create ho gaya!",
                title="Sales Order Created",
                indicator="green"
            )

        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Shree→ERPNext SO Error: {self.name}")
            frappe.throw(
                "ERPNext Sales Order create karne mein error aaya. "
                "Error log check karo ya admin se contact karo."
            )

    # ──────────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────────

    def _load_customer_details(self):
        if not self.customer:
            return

        if not self.company:
            self.company = (
                frappe.defaults.get_user_default("Company")
                or frappe.db.get_single_value("Global Defaults", "default_company")
            )

        billing = _get_address(self.customer, primary=True)
        if billing:
            self.customer_address = billing
            self.address_display  = _format_address(billing)

        shipping = _get_address(self.customer, shipping=True)
        if shipping:
            self.shipping_address_name = shipping
            self.shipping_address      = _format_address(shipping)
        elif billing:
            self.shipping_address_name = billing
            self.shipping_address      = self.address_display

    def _set_item_amounts(self):
        for item in self.items:
            item.amount = flt(item.qty) * flt(item.rate)

    def _calculate_totals(self):
        self.grand_total = sum(flt(d.amount) for d in self.items)
        self.total_qty   = sum(flt(d.qty)    for d in self.items)

    def _validate_items(self):
        if not self.items:
            frappe.throw("Kam se kam ek item add karo.")
        for i, row in enumerate(self.items, 1):
            if not row.item_code:
                frappe.throw(f"Row {i}: Item Code zaroori hai.")
            if flt(row.qty) <= 0:
                frappe.throw(f"Row {i}: Quantity 0 se zyada honi chahiye.")
            if flt(row.rate) <= 0:
                frappe.throw(f"Row {i}: Rate 0 se zyada hona chahiye.")


# ──────────────────────────────────────────────────────────
#  Utility functions
# ──────────────────────────────────────────────────────────

def _get_customer_for_user(user):
    if not user or user in ("Administrator", "Guest"):
        return None

    contact = frappe.db.get_value("Contact", {"user": user}, "name")
    if contact:
        customer = frappe.db.get_value(
            "Dynamic Link",
            {"parent": contact, "link_doctype": "Customer", "parenttype": "Contact"},
            "link_name",
        )
        if customer:
            return customer

    return frappe.db.get_value("Portal User", {"user": user}, "parent") or None


def _get_address(customer, primary=False, shipping=False):
    linked = frappe.db.get_all(
        "Dynamic Link",
        filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
        pluck="parent"
    )
    if not linked:
        return None

    filters = {"name": ["in", linked]}
    if primary:
        filters["is_primary_address"] = 1
    if shipping:
        filters["is_shipping_address"] = 1

    return frappe.db.get_value("Address", filters, "name")


def _format_address(address_name):
    if not address_name:
        return ""
    try:
        from frappe.contacts.doctype.address.address import get_address_display
        return get_address_display(address_name) or ""
    except Exception:
        row = frappe.db.get_value(
            "Address", address_name,
            ["address_line1", "address_line2", "city", "state", "pincode", "country"],
            as_dict=True,
        )
        if row:
            return ", ".join(v for v in row.values() if v)
    return ""


# ──────────────────────────────────────────────────────────
#  Whitelisted API  (called from JS)
# ──────────────────────────────────────────────────────────

@frappe.whitelist()
def get_customer_details_for_user():
    user = frappe.session.user
    customer_name = _get_customer_for_user(user)
    if not customer_name:
        return {}

    result = {
        "customer":      customer_name,
        "customer_name": frappe.db.get_value("Customer", customer_name, "customer_name"),
        "company": (
            frappe.defaults.get_user_default("Company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
        ),
    }

    billing = _get_address(customer_name, primary=True)
    if billing:
        result["customer_address"] = billing
        result["address_display"]  = _format_address(billing)

    shipping = _get_address(customer_name, shipping=True)
    if shipping:
        result["shipping_address_name"] = shipping
        result["shipping_address"]       = _format_address(shipping)
    elif billing:
        result["shipping_address_name"] = billing
        result["shipping_address"]       = result.get("address_display", "")

    return result


@frappe.whitelist()
def get_item_details(item_code):
    if not item_code:
        return {}

    item = frappe.get_cached_doc("Item", item_code)
    uom  = item.sales_uom if item.sales_uom else item.stock_uom

    currency = (
        frappe.defaults.get_user_default("Currency")
        or frappe.db.get_single_value("Global Defaults", "default_currency")
        or "INR"
    )
    rate = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "selling": 1, "currency": currency},
        "price_list_rate",
    ) or 0.0

    return {
        "uom":        uom,
        "rate":       flt(rate),
        "item_name":  item.item_name,
        "item_image": item.image or "",
    }
