# Copyright (c) 2025, atul and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname

class CustomerVisit(Document):
    def autoname(self):
        # Ensure year is selected
        if not self.year:
            frappe.throw("Please select Year before saving.")

        # Build prefix dynamically
        prefix = f"CV-{self.year}-"

        # Use frappe's naming_series function to auto increment
        self.name = make_autoname(prefix + ".#####")
