# Copyright (c) 2025, atul and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime, add_to_date
import json

class SalesSession(Document):
	def on_submit(self, method=None):
		create_sales_orders(items=self.items,customers=self.customer, name=self.name)
	def on_cancel(self, method=None):
		doc = frappe.db.exists("Sales Order",{"custom_sales_session":self.name,"docstatus":0})
		if doc:
			frappe.throw("Sales Orders are linked with this document, Can't cancel")


@frappe.whitelist()
def get_qty(item_code, warehouse):
	qty = frappe.db.sql(f"""SELECT actual_qty as qty
			FROM `tabBin` Where item_code = '{item_code}' and warehouse = '{warehouse}'
			ORDER BY creation DESC
			LIMIT 1;
			""",as_dict=1)
	return qty

@frappe.whitelist()
def get_uom(item_code):
	uom = frappe.db.sql(f""" select uom,conversion_factor from `tabUOM Conversion Detail`
				where parent='{item_code}' """,as_dict=1)
	return uom


def create_sales_orders(items, customers, name):
	seq = ['first','second','third','fourth','fifth','sixth']
	try:
		for cust in range(len(customers)):
			so = frappe.new_doc("Sales Order")
			so.customer = customers[cust].get("customer")
			so.posting_date = nowdate()
			so.posting_time = nowtime()
			so.due_date = add_to_date(nowdate(), days=7)
			so.custom_sales_session = name
			for item in items:
				if item.get(f"{seq[cust]}_order_qty"):
					so.append('items',{
						"item_code":item.get("item_code"),
						"item_name":item.get("item_name"),
						"qty":item.get(f"{seq[cust]}_order_qty"),
						"amount":item.get(f"{seq[cust]}_order_amount"),
						"rate":item.get("rate"),
						"delivery_date":nowdate()
					})
			so.run_method("set_missing_values")
			so.run_method("calculate_taxes_and_total")
			so.save()
		frappe.msgprint("Sales Orders Created Successfully")
	except Exception as e:
		frappe.throw("Error occured")

			