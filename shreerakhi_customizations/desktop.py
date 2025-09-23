from frappe import _

def get_data():
    return [
        {
            "module_name": "Shree",   # App/module name
            "color": "blue",
            "icon": "octicon octicon-file-directory",
            "type": "module",         # ✅ always 'module' for Desk card
            "label": _("Shree")
        }
    ]



from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"module_name": "Victory",
			"color": "grey",
			"icon": "octicon octicon-file-directory",
			"type": "module",
			"label": _("Victory")
		},
		
	]