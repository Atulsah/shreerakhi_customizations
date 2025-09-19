import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)   # 👈 ये change करो
def get_sales_invoice_series():
    """
    Return available naming series options for Sales Invoice
    """
    try:
        series = frappe.get_meta("Sales Invoice").get_field("naming_series").options
        if not series:
            return []
        return [s.strip() for s in series.split("\n") if s.strip()]
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Error in get_sales_invoice_series"))
        return []
