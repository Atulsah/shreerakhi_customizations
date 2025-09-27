'''
import frappe
import json

def execute():
    workspace_name = "Shree"

    if frappe.db.exists("Workspace", workspace_name):
        ws = frappe.get_doc("Workspace", workspace_name)
        print(f"Updating existing workspace: {workspace_name}")
    else:
        ws = frappe.new_doc("Workspace")
        ws.name = workspace_name
        print(f"Creating new workspace: {workspace_name}")

    # Define content as a list of blocks
    content_blocks = [
        {
            "type": "header",
            "data": {
                "text": "Shree Workspace",
                "level": 1
            }
        }
    ]

    ws.update({
        "title": "Shree",
        "module": "Shree",
        "label": "Shree",
        "public": 1,
        "is_hidden": 0,
        "icon": "retail",
        "sequence_id": 28,
        "links": [
            {"type": "Card Break", "label": "Masters"},
            {"type": "Link", "link_type": "DocType", "label": "Shree Temp Range", "link_to": "Shree Temp Range"},
            {"type": "Link", "link_type": "DocType", "label": "Item Range", "link_to": "Item Range"},
            {"type": "Link", "link_type": "DocType", "label": "Factory Location", "link_to": "Factory Location"},
            {"type": "Link", "link_type": "DocType", "label": "Item Category", "link_to": "Item Category"},
            {"type": "Card Break", "label": "Documents"},
            {"type": "Link", "link_type": "DocType", "label": "Shree Packing List", "link_to": "Shree Packing List"},
            {"type": "Card Break", "label": "Reports"},
            {"type": "Link", "link_type": "Report", "label": "Customer Item Catalogue", "link_to": "Customer Item Catalogue", "report_ref_doctype": "Item"},
        ],
        "shortcuts": [
            {"type": "DocType", "label": "Shree Packing List", "link_to": "Shree Packing List"},
            {"type": "DocType", "label": "Shree Temp Range", "link_to": "Shree Temp Range"},
            {"type": "DocType", "label": "Factory Location", "link_to": "Factory Location"},
            {"type": "DocType", "label": "Item Category", "link_to": "Item Category"},
            {"type": "DocType", "label": "Item Range", "link_to": "Item Range"},
            {"type": "Report", "label": "Customer Item Catalogue", "link_to": "Customer Item Catalogue", "report_ref_doctype": "Item"},
        ],
        "onboardings": [],
        "content": json.dumps(content_blocks)  # must be JSON string
    })

    ws.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"✅ Workspace '{workspace_name}' created/updated successfully")
'''
'''
import frappe
import json

def execute():
    workspace_name = "Shree"

    # Check if workspace exists
    if frappe.db.exists("Workspace", workspace_name):
        ws = frappe.get_doc("Workspace", workspace_name)
        print(f"Updating existing workspace: {workspace_name}")
    else:
        ws = frappe.new_doc("Workspace")
        ws.name = workspace_name
        print(f"Creating new workspace: {workspace_name}")

    # Define workspace content blocks
    content_blocks = [
        # Header
        {"type": "header", "data": {"text": "Shree Workspace", "level": 1}},

        # Masters card
        {"type": "card", "data": {"label": "Masters", "items": [
            {"type": "link", "label": "Shree Temp Range", "link_to": "Shree Temp Range"},
            {"type": "link", "label": "Item Range", "link_to": "Item Range"},
            {"type": "link", "label": "Factory Location", "link_to": "Factory Location"},
            {"type": "link", "label": "Item Category", "link_to": "Item Category"}
        ]}},

        # Documents card
        {"type": "card", "data": {"label": "Documents", "items": [
            {"type": "link", "label": "Shree Packing List", "link_to": "Shree Packing List"}
        ]}},

        # Reports card
        {"type": "card", "data": {"label": "Reports", "items": [
            {"type": "link", "label": "Customer Item Catalogue", "link_to": "Customer Item Catalogue"}
        ]}}
    ]

    # Update workspace fields
    ws.update({
        "title": "Shree",
        "module": "Shree",
        "label": "Shree",
        "public": 1,
        "is_hidden": 0,
        "icon": "retail",
        "sequence_id": 28,
        "content": json.dumps(content_blocks),
        "onboardings": [],  # must exist
        "shortcuts": [
            {"type": "DocType", "label": "Shree Packing List", "link_to": "Shree Packing List"},
            {"type": "DocType", "label": "Shree Temp Range", "link_to": "Shree Temp Range"},
            {"type": "DocType", "label": "Factory Location", "link_to": "Factory Location"},
            {"type": "DocType", "label": "Item Category", "link_to": "Item Category"},
            {"type": "DocType", "label": "Item Range", "link_to": "Item Range"},
            {"type": "Report", "label": "Customer Item Catalogue", "link_to": "Customer Item Catalogue", "report_ref_doctype": "Item"},
        ]
    })

    # Save and commit
    ws.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"✅ Workspace '{workspace_name}' created/updated successfully")
'''

import frappe
import json

def execute():
    workspace_name = "Shree"

    # Check if workspace exists
    if frappe.db.exists("Workspace", workspace_name):
        ws = frappe.get_doc("Workspace", workspace_name)
        print(f"Updating existing workspace: {workspace_name}")
    else:
        ws = frappe.new_doc("Workspace")
        ws.name = workspace_name
        print(f"Creating new workspace: {workspace_name}")

    # HTML block for all links
    html_block = {
        "type": "html",
        "data": """
            <h2>Masters</h2>
            <ul>
                <li><a href="/app/shree-temp-range">Shree Temp Range</a></li>
                <li><a href="/app/item-range">Item Range</a></li>
                <li><a href="/app/factory-location">Factory Location</a></li>
                <li><a href="/app/item-category">Item Category</a></li>
            </ul>

            <h2>Documents</h2>
            <ul>
                <li><a href="/app/shree-packing-list">Shree Packing List</a></li>
            </ul>

            <h2>Reports</h2>
            <ul>
                <li><a href="/app/customer-item-catalogue">Customer Item Catalogue</a></li>
            </ul>
        """
    }

    # Build content blocks
    content_blocks = [
        {"type": "header", "data": {"text": "Shree Workspace", "level": 1}},
        html_block
    ]

    # Update workspace fields
    ws.update({
        "title": "Shree",
        "module": "Shree",
        "label": "Shree",
        "public": 1,
        "is_hidden": 0,
        "icon": "retail",
        "sequence_id": 28,
        "content": json.dumps(content_blocks),
        "onboardings": [],  # must exist
        "shortcuts": [
            {"type": "DocType", "label": "Shree Packing List", "link_to": "Shree Packing List"},
            {"type": "DocType", "label": "Shree Temp Range", "link_to": "Shree Temp Range"},
            {"type": "DocType", "label": "Factory Location", "link_to": "Factory Location"},
            {"type": "DocType", "label": "Item Category", "link_to": "Item Category"},
            {"type": "DocType", "label": "Item Range", "link_to": "Item Range"},
            {"type": "Report", "label": "Customer Item Catalogue", "link_to": "Customer Item Catalogue", "report_ref_doctype": "Item"},
        ]
    })

    # Save and commit
    ws.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"✅ Workspace '{workspace_name}' created/updated successfully")

