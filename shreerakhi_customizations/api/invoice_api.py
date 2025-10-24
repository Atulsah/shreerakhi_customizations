import frappe
import uuid
from frappe import _

def generate_public_access_key(doc, method):
    """Assign a unique secure key when invoice is submitted."""
    if not doc.custom_public_access_key:
        key = str(uuid.uuid4())
        doc.db_set("custom_public_access_key", key, update_modified=False)
        frappe.db.commit()


# CRITICAL: No decorator here, we'll handle auth in the function
def view_invoice():
    """
    Serve Sales Invoice PDF to guest users securely using a key.
    This is a raw endpoint without @frappe.whitelist decorator
    """
    # Get key from request
    key = frappe.form_dict.get('key')
    
    if not key:
        frappe.respond_as_web_page(
            _("Invalid Link"),
            _("No access key provided"),
            http_status_code=400,
            indicator_color='red'
        )
        return

    # Query database directly (bypasses permissions)
    invoice = frappe.db.get_value(
        "Sales Invoice",
        {"custom_public_access_key": key, "docstatus": 1},
        ["name", "customer_name"],
        as_dict=True
    )

    if not invoice:
        frappe.respond_as_web_page(
            _("Invalid Link"),
            _("Invoice not found or link has expired"),
            http_status_code=404,
            indicator_color='red'
        )
        return

    invoice_name = invoice.name

    # Generate PDF with admin privileges
    try:
        # Temporarily elevate to Administrator
        frappe.set_user("Administrator")
        frappe.flags.ignore_permissions = True
        
        # Get the print format HTML
        html = frappe.get_print(
            "Sales Invoice",
            invoice_name,
            print_format="Bill of Supply - Shree"
        )
        
        # Convert to PDF
        from frappe.utils.pdf import get_pdf
        pdf_data = get_pdf(html)
        
    except Exception as e:
        frappe.log_error(f"PDF Generation Error: {str(e)}", "Invoice PDF Error")
        frappe.respond_as_web_page(
            _("Error"),
            _("Unable to generate invoice. Please contact support."),
            http_status_code=500,
            indicator_color='red'
        )
        return
    finally:
        frappe.flags.ignore_permissions = False
        frappe.set_user("Guest")

    # Send PDF as download
    frappe.local.response.filename = f"{invoice_name}.pdf"
    frappe.local.response.filecontent = pdf_data
    frappe.local.response.type = "pdf"