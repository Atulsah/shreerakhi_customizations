import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import _


class ShreePackingList(Document):

    def on_submit(self):
        self.create_sales_invoice()

    # -----------------------
    # Tax Helper Functions
    # -----------------------
    def get_item_tax_template_from_item_or_group(self, item_code):
        """
        Fetch Item Tax Template first from the Item's own 'taxes' table.
        If not found there, fall back to the Item's Item Group 'taxes' table.
        """
        item_taxes = frappe.get_all(
            "Item Tax",
            filters={"parent": item_code, "parenttype": "Item"},
            fields=["item_tax_template", "minimum_net_rate", "maximum_net_rate"],
            order_by="idx asc",
        )
        template = self._pick_applicable_template(item_taxes)
        if template:
            return template

        item_group = frappe.db.get_value("Item", item_code, "item_group")
        if item_group:
            group_taxes = frappe.get_all(
                "Item Tax",
                filters={"parent": item_group, "parenttype": "Item Group"},
                fields=["item_tax_template", "minimum_net_rate", "maximum_net_rate"],
                order_by="idx asc",
            )
            template = self._pick_applicable_template(group_taxes)
            if template:
                return template

        return None

    def _pick_applicable_template(self, rows):
        """Pick the first template with no restrictive min/max net rate slab."""
        for r in rows:
            min_rate = flt(r.get("minimum_net_rate"))
            max_rate = flt(r.get("maximum_net_rate"))
            if min_rate == 0 and max_rate == 0:
                return r.get("item_tax_template")
        if rows:
            return rows[0].get("item_tax_template")
        return None

    def get_default_sales_taxes_template(self, company):
        """Fetch the company's default Sales Taxes and Charges Template."""
        if not company:
            return None
        return frappe.db.get_value(
            "Sales Taxes and Charges Template",
            {"company": company, "is_default": 1},
            "name",
        )

    def apply_taxes_template_to_invoice(self, invoice, template_name):
        """Copy tax rows from a Sales Taxes and Charges Template into the invoice."""
        if not template_name:
            return
        template = frappe.get_doc("Sales Taxes and Charges Template", template_name)
        invoice.taxes_and_charges = template.name
        for tax in template.get("taxes") or []:
            invoice.append("taxes", {
                "charge_type": tax.charge_type,
                "account_head": tax.account_head,
                "description": tax.description,
                "rate": tax.rate,
                "cost_center": tax.cost_center,
                "included_in_print_rate": tax.included_in_print_rate,
            })

    def copy_taxes_from_sales_order(self, invoice, so):
        """Copy header-level taxes directly from the linked Sales Order."""
        invoice.taxes_and_charges = so.taxes_and_charges
        for tax in so.get("taxes") or []:
            invoice.append("taxes", {
                "charge_type": tax.charge_type,
                "account_head": tax.account_head,
                "description": tax.description,
                "rate": tax.rate,
                "cost_center": tax.cost_center,
                "included_in_print_rate": tax.included_in_print_rate,
            })

    def add_tax_rows_from_item_tax_templates(self, invoice, item_tax_templates):
        """
        Item Tax Template only overrides rates for accounts that already
        exist in the invoice's header 'taxes' table. If that table is empty
        (no company default template, no SO taxes), nothing gets calculated.

        So here we read each Item Tax Template's own child 'taxes' table
        (account_head + tax_rate) and add ONLY genuine "Output Tax" account
        heads to the header - skipping RCM, Refund, and Input Tax variants,
        since those belong to Purchase-side / GST return logic, not to a
        Sales Invoice.

        NOTE: This name-based filter is a safety net. The permanent, more
        reliable fix is to clean up the Item Tax Template itself so it only
        contains the Output Tax account rows that are actually applicable
        (see conversation notes).
        """
        existing_accounts = {row.account_head for row in (invoice.get("taxes") or [])}
        skip_keywords = ["rcm", "refund", "input tax"]

        for template_name in item_tax_templates:
            if not template_name:
                continue
            try:
                template = frappe.get_doc("Item Tax Template", template_name)
            except frappe.DoesNotExistError:
                continue

            for row in template.get("taxes") or []:
                account_head = row.tax_type
                if not account_head or account_head in existing_accounts:
                    continue

                account_lower = account_head.lower()

                # Skip anything that isn't a plain Output Tax row
                if any(keyword in account_lower for keyword in skip_keywords):
                    continue
                if "output tax" not in account_lower:
                    continue

                invoice.append("taxes", {
                    "charge_type": "On Net Total",
                    "account_head": account_head,
                    "description": account_head,
                    "rate": 0,  # actual rate comes from item_tax_template override per item
                })
                existing_accounts.add(account_head)

    # -----------------------
    # Main Sales Invoice Creation
    # -----------------------
    def create_sales_invoice(self):
        """Create Sales Invoice from Packing Boxes, with proper tax calculation."""
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

        so_doc = None
        so_item_map = {}
        if getattr(self, "sales_order", None):
            so_doc = frappe.get_doc("Sales Order", self.sales_order)
            for so_item in so_doc.get("items") or []:
                so_item_map[so_item.item_code] = so_item

        invoice = frappe.new_doc("Sales Invoice")
        if getattr(self, "invoice_series", None):
            invoice.naming_series = self.invoice_series

        invoice.customer = self.customer
        if getattr(self, "sales_order", None):
            invoice.sales_order = self.sales_order

        # ---- Set Company (required for tax logic) ----
        company = (
            getattr(self, "company", None)
            or (so_doc.company if so_doc else None)
            or frappe.defaults.get_user_default("Company")
            or frappe.defaults.get_global_default("company")
        )
        invoice.company = company

        # ---- Header level Taxes and Charges (Step 1: SO / company default if available) ----
        if so_doc and so_doc.get("taxes"):
            self.copy_taxes_from_sales_order(invoice, so_doc)
        else:
            default_template = self.get_default_sales_taxes_template(company)
            self.apply_taxes_template_to_invoice(invoice, default_template)

        # ---- Add Items with proper rate + item_tax_template ----
        item_tax_templates_used = set()
        for key, data in item_map.items():
            row = invoice.append("items", {})
            row.item_code = data["item_code"]
            row.qty = flt(data["qty"])
            if data.get("uom"):
                row.uom = data["uom"]

            rate = 0
            so_detail = None
            item_tax_template = None

            so_item = so_item_map.get(data["item_code"])
            if so_item:
                rate = so_item.rate or 0
                so_detail = so_item.name
                item_tax_template = getattr(so_item, "item_tax_template", None)

            if not rate:
                price = frappe.db.get_value(
                    "Item Price", {"item_code": data["item_code"]}, "price_list_rate"
                )
                rate = price or 0

            # Fallback: Item -> Item Group tax template if SO didn't carry one
            if not item_tax_template:
                item_tax_template = self.get_item_tax_template_from_item_or_group(data["item_code"])

            row.rate = rate
            if item_tax_template:
                row.item_tax_template = item_tax_template
                item_tax_templates_used.add(item_tax_template)

            if getattr(self, "sales_order", None):
                row.sales_order = self.sales_order
                if so_detail:
                    row.so_detail = so_detail

        # ---- Step 2 (THE FIX): Ensure header has Output Tax account rows ----
        self.add_tax_rows_from_item_tax_templates(invoice, item_tax_templates_used)

        # ---- Ensure missing values (price list, currency, etc.) are filled ----
        invoice.set_missing_values()

        # ---- Recalculate taxes and totals explicitly before insert ----
        invoice.calculate_taxes_and_totals()

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