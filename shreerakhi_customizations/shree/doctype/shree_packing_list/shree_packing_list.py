import frappe
from frappe.model.document import Document
from frappe.utils import flt

class ShreePackingList(Document):
    def on_submit(self):
        # जब Packing List submit हो तब Sales Invoice create करो
        self.create_sales_invoice()

    def create_sales_invoice(self):
        """
        Create (save only) a Sales Invoice from this Packing List.
        Uses child table field `qty` for quantities and links Sales Order properly.
        """
        # Aggregate items from child table
        item_map = {}
        for d in self.get("shree_packing_boxes") or []:
            item_code = getattr(d, "item_code", None)
            if not item_code:
                continue

            qty = flt(getattr(d, "qty", None) or 0)
            uom = getattr(d, "uom", None) or frappe.db.get_value("Item", item_code, "stock_uom")

            key = (item_code, uom)
            if key not in item_map:
                item_map[key] = {"item_code": item_code, "uom": uom, "qty": 0.0}
            item_map[key]["qty"] += qty

        if not item_map:
            frappe.msgprint("No items found in Packing Boxes to create Sales Invoice.")
            return

        # Build Sales Invoice
        invoice = frappe.new_doc("Sales Invoice")

        # Naming Series (from Packing List)
        if getattr(self, "invoice_series", None):
            invoice.naming_series = self.invoice_series

        # Customer & Sales Order link
        invoice.customer = self.customer
        if getattr(self, "sales_order", None):
            invoice.sales_order = self.sales_order

        # Add aggregated items
        for key, data in item_map.items():
            row = invoice.append("items", {})
            row.item_code = data["item_code"]
            row.qty = flt(data["qty"])
            if data.get("uom"):
                row.uom = data["uom"]

            rate = 0
            so_detail = None

            # Try to fetch rate & so_detail from Sales Order
            if getattr(self, "sales_order", None):
                so_item = frappe.db.get_value(
                    "Sales Order Item",
                    {"parent": self.sales_order, "item_code": data["item_code"]},
                    ["name", "rate"],
                    as_dict=True,
                )
                if so_item:
                    rate = so_item.get("rate") or 0
                    so_detail = so_item.get("name")

            # If no SO rate, try Item Price
            if not rate:
                price = frappe.db.get_value(
                    "Item Price",
                    {"item_code": data["item_code"]},
                    "price_list_rate"
                )
                rate = price or 0

            row.rate = rate

            # Link back to Sales Order & SO Item
            if getattr(self, "sales_order", None):
                row.sales_order = self.sales_order
                if so_detail:
                    row.so_detail = so_detail

        # Save invoice as Draft
        invoice.insert(ignore_permissions=True)

        # Link invoice back to Packing List
        self.db_set("sales_invoice", invoice.name)

        # Success message with clickable link
        link = f'#Form/Sales Invoice/{invoice.name}'
        frappe.msgprint(
            f'Sales Invoice <a href="{link}"><b>{invoice.name}</b></a> has been created and linked to this Packing List.',
            alert=True
        )
