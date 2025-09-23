import frappe
from frappe.utils import get_url
from frappe.utils.pdf import get_pdf
from frappe import _

def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": "Image Link", "fieldname": "image_link", "fieldtype": "HTML", "width": 150},  # Clickable in ERPNext
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 100},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 100},
        {"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 100},
        {"label": "Item Range", "fieldname": "item_range", "fieldtype": "Data", "width": 100},
        {"label": "Item Range Name", "fieldname": "item_range_name", "fieldtype": "Data", "width": 100},
        {"label": "Box Type", "fieldname": "box_type", "fieldtype": "Data", "width": 100},
        {"label": "Item Category", "fieldname": "item_category", "fieldtype": "Data", "width": 100},
        {"label": "Available Qty", "fieldname": "available_qty", "fieldtype": "Int", "width": 100},
        {"label": "Stock UOM", "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 100},
        {"label": "Selling Price", "fieldname": "selling_price", "fieldtype": "Currency", "width": 100}
    ]

    price_list = (filters or {}).get("price_list") or "Standard Selling"
    base_url = get_url()
    data = []

    sql_query = """
        SELECT 
            i.image AS image,
            i.item_code,
            i.item_name,
            i.item_group,
            IFNULL(i.custom_item_range, '') AS item_range,
            IFNULL(i.custom_item_range_name, '') AS item_range_name,
            IFNULL(i.custom_box_type, '') AS box_type,
            IFNULL(i.custom_item_category, '') AS item_category,
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
                (i.item_group LIKE 'Semi Finish Goods%%' 
                 AND (bin.actual_qty - IFNULL((SELECT SUM(si_item.qty) 
                                               FROM `tabSales Invoice Item` si_item
                                               JOIN `tabSales Invoice` si ON si.name = si_item.parent
                                               WHERE si_item.item_code = i.item_code 
                                                 AND si.docstatus = 0),0)) > 5000)
                OR
                (i.item_group LIKE 'Finish Goods%%' 
                 AND (bin.actual_qty - IFNULL((SELECT SUM(si_item.qty) 
                                               FROM `tabSales Invoice Item` si_item
                                               JOIN `tabSales Invoice` si ON si.name = si_item.parent
                                               WHERE si_item.item_code = i.item_code 
                                                 AND si.docstatus = 0),0)) > 25)
            )
    """

    try:
        data = frappe.db.sql(sql_query, {"price_list": price_list}, as_dict=1) or []
    except Exception as e:
        frappe.log_error(f"Customer Item Catalogue query failed: {e}")

    # Process data
    for row in data:
        # Convert Available Qty to integer
        if row.get("available_qty") is not None:
            row["available_qty"] = int(row["available_qty"])

        img = row.get("image")
        if img:
            if not img.startswith("http"):
                img = f"{base_url}{img}"

            # PDF render
            row["image_html"] = f"""
                <img src="{img}" 
                     style="width:120px; height:120px; object-fit:contain; border:1px solid #ddd; border-radius:6px;">
            """

            # ERPNext report → clickable link
            row["image_link"] = f'<a href="{img}" target="_blank">{img}</a>'
        else:
            row["image_html"] = """
                <div style="width:120px; height:120px; border:1px solid #eee; background:#fafafa;"></div>
            """
            row["image_link"] = "No Image"

    return columns, data

@frappe.whitelist()
def download_customer_catalogue(price_list=None):
    columns, data = execute(filters={"price_list": price_list})

    base_url = get_url()
    context = {
        "items": data,
        "price_list": price_list,
        "base_url": base_url,
    }

    html = frappe.render_template(
        "shreerakhi_customizations/templates/includes/customer_catalogue_template.html",
        context
    )

    try:
        pdf_content = get_pdf(html)
    except Exception:
        frappe.throw(_("PDF generation failed (check image links or wkhtmltopdf setup)."))

    frappe.local.response.filename = "Customer_Catalogue.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"
