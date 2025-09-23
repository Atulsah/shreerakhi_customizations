from frappe import _

def get_data():
    return [
        {
            "label": _("Master"),
            "items": [
                {"type": "doctype", "name": "Item Category", "label": _("Item Category")},
                {"type": "doctype", "name": "Item Range", "label": _("Item Range")},
                {"type": "doctype", "name": "Factory Location", "label": _("Factory Location")},
                {"type": "doctype", "name": "Shree Packing List", "label": _("Shree Packing List")},
            ]
        },
        {
            "label": _("Reports"),
            "items": [
                {
                    "type": "report", "is_query_report": True, "name": "Customer Item Catalogue",
                    "doctype": "Item", "label": _("Customer Item Catalogue"),
                }
            ]
        }
    ]
