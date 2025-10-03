import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import _

class ShreePackingList(Document):

    def on_submit(self):
        self.create_sales_invoice()

    def create_sales_invoice(self):
        """Create Sales Invoice from Packing Boxes"""
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

        if getattr(self, "sales_invoice", None):
            frappe.msgprint(f"Sales Invoice {self.sales_invoice} already exists.")
            return

        invoice = frappe.new_doc("Sales Invoice")
        if getattr(self, "invoice_series", None):
            invoice.naming_series = self.invoice_series

        invoice.customer = self.customer
        if getattr(self, "sales_order", None):
            invoice.sales_order = self.sales_order

        for key, data in item_map.items():
            row = invoice.append("items", {})
            row.item_code = data["item_code"]
            row.qty = flt(data["qty"])
            if data.get("uom"):
                row.uom = data["uom"]

            rate = 0
            so_detail = None
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

            if not rate:
                price = frappe.db.get_value("Item Price", {"item_code": data["item_code"]}, "price_list_rate")
                rate = price or 0

            row.rate = rate
            if getattr(self, "sales_order", None):
                row.sales_order = self.sales_order
                if so_detail:
                    row.so_detail = so_detail

        invoice.insert(ignore_permissions=True)
        self.db_set("sales_invoice", invoice.name)
        link = f'#Form/Sales Invoice/{invoice.name}'
        frappe.msgprint(
            f'Sales Invoice <a href="{link}"><b>{invoice.name}</b></a> has been created and linked to this Packing List.',
            alert=True
        )

    # -----------------------
    # Cancel & Delete Hooks
    # -----------------------
    def before_cancel(self):
        if self.sales_invoice:
            try:
                si = frappe.get_doc("Sales Invoice", self.sales_invoice)
                self.db_set("sales_invoice", None)

                if si.docstatus == 1:
                    try:
                        si.cancel()
                        frappe.msgprint(f"Linked Submitted Sales Invoice {si.name} cancelled.")
                    except frappe.LinkExistsError:
                        frappe.msgprint(f"Cannot cancel Sales Invoice {si.name} due to linked GL/Payment entries.")
                        frappe.throw(f"Cannot cancel Sales Invoice {si.name} due to linked documents.")
                elif si.docstatus == 0:
                    si.delete()
                    frappe.msgprint(f"Linked Draft Sales Invoice {si.name} deleted.")

            except frappe.DoesNotExistError:
                frappe.msgprint(f"Linked Sales Invoice {self.sales_invoice} not found.")
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "Error in before_cancel")
                frappe.throw(f"Could not cancel/delete linked Sales Invoice: {str(e)}")

    def before_delete(self):
        if self.sales_invoice:
            try:
                si = frappe.get_doc("Sales Invoice", self.sales_invoice)
                self.db_set("sales_invoice", None)

                if si.docstatus == 1:
                    try:
                        si.cancel()
                        frappe.msgprint(f"Linked Submitted Sales Invoice {si.name} cancelled.")
                    except frappe.LinkExistsError:
                        frappe.msgprint(f"Cannot cancel Sales Invoice {si.name} due to linked GL/Payment entries.")
                        frappe.throw(f"Cannot cancel Sales Invoice {si.name} due to linked documents.")
                elif si.docstatus == 0:
                    si.delete()
                    frappe.msgprint(f"Linked Draft Sales Invoice {si.name} deleted.")

            except frappe.DoesNotExistError:
                frappe.msgprint(f"Linked Sales Invoice {self.sales_invoice} not found.")
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "Error in before_delete")
                frappe.throw(f"Could not delete linked Sales Invoice: {str(e)}")