// Copyright (c) 2025, atul and contributors
// For license information, please see license.txt
/*
frappe.ui.form.on('Customer Visit', {
    onload: function(frm) {
        // Fetch the options from Address Doctype field dynamically
        frappe.db.get_doc('DocType', 'Address').then(address_doctype => {
            let state_field = address_doctype.fields.find(f => f.fieldname === 'state');
            if (state_field && state_field.options) {
                let states = state_field.options.split('\n');
                frm.set_df_property('state', 'options', states.join('\n'));
            }
        });
    },

    refresh: function(frm) {
        // Show/hide buttons
        toggle_buttons(frm);

        // Calculate days before D-Day
        calculate_days_before(frm);
    },

    d_day: function(frm) {
        calculate_days_before(frm);
    },

    customer_type: function(frm) {
        toggle_buttons(frm);
    },

    customer: function(frm) {
        if (frm.doc.customer) {
            frappe.db.get_doc('Customer', frm.doc.customer).then(customer_doc => {

                // Fetch linked Address (first one found)
                frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "Address",
                        filters: {
                            link_doctype: "Customer",
                            link_name: frm.doc.customer
                        },
                        fields: [
                            "address_title", "address_line1", "address_line2",
                            "city", "state", "pincode", "phone", "gstin"
                        ],
                        limit: 1
                    },
                    callback: function(r) {
                        let address_html = "";
                        let details_html = "";

                        if (r.message && r.message.length > 0) {
                            let addr = r.message[0];
                            let full_address = `
                                ${addr.address_line1 || ''}<br>
                                ${addr.address_line2 || ''}<br>
                                ${addr.city || ''}, ${addr.state || ''} - ${addr.pincode || ''}<br>
                            `;

                            address_html = `
                                <div style="line-height:1.5; font-size:13px;">
                                    <b>Address:</b><br>${full_address}
                                    <b>Contact:</b> ${addr.phone || ''}<br>
                                    <b>GSTIN:</b> ${addr.gstin || ''}<br>
                                </div>
                            `;

                            details_html = `
                                <b>Name:</b> ${customer_doc.customer_name}<br>
                                <b>Address:</b> ${addr.address_line1 || ''}, ${addr.city || ''}<br>
                                <b>Contact:</b> ${addr.phone || ''}<br>
                                <b>GSTIN:</b> ${addr.gstin || ''}<br>
                            `;
                        } else {
                            // No address found
                            details_html = `<b>Name:</b> ${customer_doc.customer_name}<br><span style="color:gray;">No address found</span>`;
                            address_html = `<span style="color:gray;">No address linked with this customer</span>`;
                        }

                        frm.set_value('customer_details', details_html);
                        frm.refresh_field('customer_details');

                        frm.fields_dict.address_html.$wrapper.html(address_html);
                    }
                });
            });
        } else {
            frm.set_value('customer_details', '');
            frm.fields_dict.address_html.$wrapper.html('');
        }
    },

    edit_customer_button: function(frm) {
        if (frm.doc.customer) {
            frappe.set_route('Form', 'Customer', frm.doc.customer);
        } else {
            frappe.msgprint('Please select a customer first');
        }
    },

    create_new_customer_button: function(frm) {
        frappe.new_doc('Customer');
    }
});

// ----------------------
// Helper Functions
// ----------------------

function calculate_days_before(frm) {
    if (frm.doc.d_day) {
        let today = frappe.datetime.get_today();
        let diff = frappe.datetime.get_diff(frm.doc.d_day, today);
        frm.set_value('days_before_d_day', diff);
    }
}

function calculate_days_before(frm){
    if(frm.doc.d_day && frm.doc.visit_date){
        frm.set_value('days_before_d_day', frappe.datetime.get_diff(frm.doc.d_day, frm.doc.visit_date));
    }
}


function toggle_buttons(frm) {
    if (frm.doc.customer_type === 'Old Customer') {
        frm.set_df_property('customer', 'reqd', 1);
        frm.set_df_property('edit_customer_button', 'hidden', 0);
        frm.set_df_property('create_new_customer_button', 'hidden', 1);
    } else if (frm.doc.customer_type === 'New Customer') {
        frm.set_df_property('customer', 'reqd', 0);
        frm.set_df_property('edit_customer_button', 'hidden', 1);
        frm.set_df_property('create_new_customer_button', 'hidden', 0);
        frm.set_value('customer', '');
        frm.set_value('customer_details', '');
        frm.fields_dict.address_html.$wrapper.html('');
    }
}
*/