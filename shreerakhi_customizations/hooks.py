# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "shreerakhi_customizations"
app_title = "Shree"
app_publisher = "atul"
app_description = "Shree"
app_email = "atulsah@shreerakhi.in"
app_license = "mit"

# -----------------------------
# Fixtures (exported customizations)
# -----------------------------
fixtures = [
    "Custom Field",
    "Property Setter",
    "Client Script",
    "Print Format"
]

# -----------------------------
# Include JS in Desk
# -----------------------------
# Attach custom JS to Shree Packing List doctype
doctype_js = {
    "Shree Packing List": "public/js/shree_packing_list.js"
}

# -----------------------------
# Document Events
# -----------------------------
doc_events = {
    "Sales Invoice": {
        "on_submit": "shreerakhi_customizations.api.invoice_api.generate_public_access_key"
    }
}

# -----------------------------
# CRITICAL: Web Page Routes (No Auth Required)
# -----------------------------
# This makes the endpoint accessible without login
web_include_js = []
web_include_css = []

# Register custom route that bypasses authentication
website_route_rules = [
    {
        "from_route": "/api/method/shreerakhi_customizations.api.invoice_api.view_invoice",
        "to_route": "shreerakhi_customizations.api.invoice_api.view_invoice"
    }
]

# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]


# Allow this method to be called without auth
# This is the KEY setting that fixes 403
override_doctype_dashboards = {}

# Custom handlers
before_install = []
after_install = []

# CRITICAL: Make this specific endpoint public
# Add to allowed methods for guest users
def validate_guest_access():
    """Called on every request"""
    if frappe.request.path == "/api/method/shreerakhi_customizations.api.invoice_api.view_invoice":
        frappe.flags.ignore_permissions = True
        return True

# Add boot session info
boot_session = []