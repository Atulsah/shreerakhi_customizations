# Copyright (c) 2025, atul and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ShreeTempRange(Document):
	def autoname(self):
		self.name = f"{self.year} - {self.temp_range_no}"
