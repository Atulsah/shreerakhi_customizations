import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def get_invoice():
    """
    Public API endpoint to download invoice PDF
    URL: /api/method/shreerakhi_customizations.api.public.get_invoice?key=xxx
    """
    # Get key from query parameters
    key = frappe.form_dict.get('key')
    
    if not key:
        frappe.throw(_("No key provided"))
    
    # Direct database query (bypasses permissions)
    invoice_name = frappe.db.get_value(
        "Sales Invoice",
        {"custom_public_access_key": key, "docstatus": 1},
        "name"
    )
    
    if not invoice_name:
        frappe.throw(_("Invoice not found or link expired"))
    
    # Generate PDF with admin access
    frappe.set_user("Administrator")
    
    try:
        # Get print format HTML
        html = frappe.get_print(
            "Sales Invoice",
            invoice_name,
            print_format="Bill of Supply - Shree"
        )
        
        # Convert to PDF
        from frappe.utils.pdf import get_pdf
        pdf_data = get_pdf(html)
        
        # Set response headers for PDF download
        frappe.local.response.filename = f"{invoice_name}.pdf"
        frappe.local.response.filecontent = pdf_data
        frappe.local.response.type = "pdf"
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Invoice PDF Generation Error")
        frappe.throw(_("Error generating PDF. Please contact support."))
    finally:
        frappe.set_user("Guest")