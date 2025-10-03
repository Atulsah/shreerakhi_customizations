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
# Whitelisted Methods
# -----------------------------
# No need to register here, since @frappe.whitelist in api/packing_list.py already handles it
