# Copyright (c) 2025, atul and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe  # type: ignore
from frappe import _  # type: ignore


def execute(filters=None):
	
	data=[]
	data = get_data(filters)
	columns = get_columns()
	"""
		if len(data) == 0:
			frappe.msgprint('No data!!!')
			return [], []
		else:
			dataframe = pd.DataFrame.from_records(data)
			data = dataframe.reset_index().to_dict('records')
	"""
	return columns, data

def get_data(filters):
	return frappe.db.sql("""
			select 
				name, customer, customer_name, place_of_supply, 
				total_qty, custom_number_of_carton, base_total, 
				additional_discount_percentage, discount_amount, 
				rounded_total, custom_bos_transporter 
			from 
				`tabSales Invoice`
		    where 
				posting_date BETWEEN %(from_date)s and %(to_date)s and 
				docstatus=1 {itm_conditions} 
			order by 
				name Asc""".format(itm_conditions=get_item_conditions(filters)),
				{'from_date':filters.from_date,'to_date':filters.to_date,
	 			'customer':filters.customer},as_dict=1) 


def get_item_conditions(filters):
	conditions = []
	if filters.get("customer"):
		conditions.append("customer=%(customer)s")	

	return "and {}".format(" and ".join(conditions)) if conditions else ""				




#Add columns in report
def get_columns():
	columns = [{"fieldname": "name","label": _("Invoice No"),"fieldtype": "Link","options": "Sales Invoice","width": 150}]
	columns.append({"fieldname": "customer_name","label": _("Customer"), "fieldtype": "Link","options": "Customer","width": 200})
	columns.append({"fieldname": "place_of_supply","label": _("Place"),"fieldtype": "Data","width": 100})
	columns.append({"fieldname": "total_qty","label": _("Quantity"),"fieldtype": "Data","width": 100})
	columns.append({"fieldname": "custom_number_of_carton","label": _("Cases"),"fieldtype": "Data","width": 100})
	columns.append({"fieldname": "base_total","label": _("Gross Amount"),"fieldtype": "Data","width": 100})
	columns.append({"fieldname": "additional_discount_percentage","label": _("Discount Pencent"),"fieldtype": "Data","width": 100})
	columns.append({"fieldname": "discount_amount","label": _("Discount"),"fieldtype": "Data","width": 100})
	columns.append({"fieldname": "rounded_total","label": _("Net Amount"),"fieldtype": "Data","width": 100})
	columns.append({"fieldname": "transport","label": _("Transport"),"fieldtype": "Data","width": 150})
		
	return columns	