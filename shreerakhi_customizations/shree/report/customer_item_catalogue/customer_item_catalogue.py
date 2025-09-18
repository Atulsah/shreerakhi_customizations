import frappe
from frappe.utils import get_url
from frappe.utils.pdf import get_pdf
from frappe import _


def execute(filters=None):
    columns = [
        {"label": "Image", "fieldname": "image", "fieldtype": "Data", "width": 220},
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"label": "Available Qty", "fieldname": "available_qty", "fieldtype": "Float", "width": 120},
        {"label": "Stock UOM", "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 100},
        {"label": "Selling Price", "fieldname": "selling_price", "fieldtype": "Currency", "width": 120},
    ]

    price_list = (filters or {}).get("price_list") or "Standard Selling"

    sql_query = """
        SELECT 
            i.image AS image,
            i.item_code,
            i.item_name,
            i.item_group,
            (bin.actual_qty 
             - IFNULL((SELECT SUM(si_item.qty) 
                       FROM `tabSales Invoice Item` si_item
                       JOIN `tabSales Invoice` si ON si.name = si_item.parent
                       WHERE si_item.item_code = i.item_code 
                         AND si.docstatus = 0), 0)
            ) AS available_qty,
            i.stock_uom,
            (SELECT ip.price_list_rate 
             FROM `tabItem Price` ip
             WHERE ip.item_code = i.item_code
               AND ip.price_list = %(price_list)s
             ORDER BY ip.valid_from DESC
             LIMIT 1) AS selling_price
        FROM 
            `tabItem` i
        JOIN 
            `tabBin` bin ON bin.item_code = i.item_code
        WHERE 
            (
                (i.item_group = 'Semi Finish Goods - 0%%' 
                 AND (bin.actual_qty - IFNULL((SELECT SUM(si_item.qty) 
                                               FROM `tabSales Invoice Item` si_item
                                               JOIN `tabSales Invoice` si ON si.name = si_item.parent
                                               WHERE si_item.item_code = i.item_code 
                                                 AND si.docstatus = 0),0)) > 5000)
                OR
                (i.item_group = 'Finish Goods - 0%%' 
                 AND (bin.actual_qty - IFNULL((SELECT SUM(si_item.qty) 
                                               FROM `tabSales Invoice Item` si_item
                                               JOIN `tabSales Invoice` si ON si.name = si_item.parent
                                               WHERE si_item.item_code = i.item_code 
                                                 AND si.docstatus = 0),0)) > 25)
            )
    """

    data = frappe.db.sql(sql_query, {"price_list": price_list}, as_dict=1)
    return columns, data


@frappe.whitelist()
def download_customer_catalogue(price_list=None):
    # Run the report
    result = execute(filters={"price_list": price_list})
    columns, data = result

    base_url = get_url()
    context = {
        "items": data,
        "price_list": price_list,
        "base_url": base_url,
    }

    # Render HTML with template
    html = frappe.render_template(
        "shreerakhi_customizations/templates/includes/customer_catalogue_template.html",
        context
    )

    # Convert to PDF
    try:
        pdf_content = get_pdf(html)
    except Exception:
        frappe.throw(_("PDF generation failed (check image links or wkhtmltopdf setup)."))

    # Return as file download
    frappe.local.response.filename = "Customer_Catalogue.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"
