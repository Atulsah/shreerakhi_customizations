// Copyright (c) 2025, atul
// For license information, please see license.txt

frappe.ui.form.on("Shree Packing List", {
    refresh: function(frm) {
        // Reset barcode field on refresh
        frm.set_value('barcode_scanner_input', '');

        // Populate invoice_series options
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
    },

    // Trigger when barcode is scanned/entered
    barcode_scanner_input: function(frm) {
        let barcode = frm.doc.barcode_scanner_input;

        if (barcode) {
            frappe.call({
                method: "shreerakhi_customizations.api.packing_list.add_box_item_by_barcode",
                args: {
                    packing_list_name: frm.doc.name,
                    barcode: barcode,
                    box_no: frm.doc.current_box_no || 1   // Agar box number field hai to use, warna 1
                },
                callback: function(r) {
                    if (r.message && r.message.status === "success") {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Error: ' + (r.message ? r.message.message : 'Unknown error')));
                    }
                }
            });

            // Barcode field reset karo taaki next scan ke liye ready ho
            frm.set_value('barcode_scanner_input', '');
        }
    }
});
