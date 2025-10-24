import frappe
from frappe import _

# NO authentication required for this page
no_cache = 1

def get_context(context):
    """
    This creates a public web page at /invoice?key=xxx
    No login required!
    """
    key = frappe.form_dict.get('key')
    
    if not key:
        frappe.throw(_("Invalid access link"))
    
    # Get invoice using the key
    invoice = frappe.db.get_value(
        "Sales Invoice",
        {"custom_public_access_key": key, "docstatus": 1},
        ["name", "customer_name", "grand_total"],
        as_dict=True
    )
    
    if not invoice:
        frappe.throw(_("Invalid or expired link"))
    
    # Generate PDF with elevated permissions
    frappe.flags.ignore_permissions = True
    try:
        html = frappe.get_print(
            "Sales Invoice",
            invoice.name,
            print_format="Bill of Supply - Shree"
        )
        
        from frappe.utils.pdf import get_pdf
        pdf_data = get_pdf(html)
        
    finally:
        frappe.flags.ignore_permissions = False
    
    # Send as PDF download
    frappe.local.response.filename = f"{invoice.name}.pdf"
    frappe.local.response.filecontent = pdf_data
    frappe.local.response.type = "pdf"