# Copyright (c) 2025, atul and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ItemCategory(Document):
	def autoname(self):
		self.name = f"{self.name1}"
