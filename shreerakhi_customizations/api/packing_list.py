import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)   
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

@frappe.whitelist()
def add_box_item_by_barcode(packing_list_name, barcode, box_no=None):
    """
    Adds or updates an item row in Shree Packing List child table based on scanned barcode.
    """
    if not packing_list_name or not barcode:
        frappe.throw(_("Packing List and Barcode are required"))

    # 1. Find item by barcode
    item = frappe.get_all("Item", filters={"barcode": barcode}, fields=["name", "stock_uom"], limit=1)
    if not item:
        return {"status": "error", "message": f"Item with barcode {barcode} not found"}

    item_code = item[0].name
    stock_uom = item[0].stock_uom

    # 2. Load Packing List
    packing_list = frappe.get_doc("Shree Packing List", packing_list_name)

    # 3. Check if item already exists in child table (same box_no)
    existing_row = None
    for row in packing_list.shree_packing_boxes:
        if row.item_code == item_code and (not box_no or row.inner_box_no == box_no or row.outer_box_no == box_no):
            existing_row = row
            break

    if existing_row:
        # If exists → increment qty
        existing_row.qty = (existing_row.qty or 0) + 1
        message = f"Quantity updated for {item_code} (now {existing_row.qty})"
    else:
        # Else → add new row
        row = packing_list.append("shree_packing_boxes", {})
        row.item_code = item_code
        row.qty = 1
        row.uom = stock_uom
        if box_no:
            row.inner_box_no = box_no
            row.outer_box_no = box_no
        message = f"Item {item_code} added to Packing List {packing_list_name}"

    # 4. Save parent
    packing_list.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": message}