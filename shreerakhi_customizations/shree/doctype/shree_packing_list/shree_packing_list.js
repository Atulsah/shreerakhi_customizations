// Copyright (c) 2025, atul and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shree Packing List", {
    refresh: function(frm) {
        if (frm.fields_dict.invoice_series) {
            frappe.call({
                method: "shreerakhi_customizations.api.packing_list.get_sales_invoice_series",
                callback: function(r) {
                    if (r.message) {
                        frm.set_df_property("invoice_series", "options", r.message);
                    }
                }
            });
        }
    }
});
