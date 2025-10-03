import frappe
from frappe import _
from frappe.utils import flt
import json

# -----------------------
# Sales Invoice Series
# -----------------------
@frappe.whitelist(allow_guest=True)
def get_sales_invoice_series():
    try:
        series = frappe.get_meta("Sales Invoice").get_field("naming_series").options
        if not series:
            return []
        return [s.strip() for s in series.split("\n") if s.strip()]
    except Exception:
        frappe.log_error(frappe.get_traceback(), _("Error in get_sales_invoice_series"))
        return []




