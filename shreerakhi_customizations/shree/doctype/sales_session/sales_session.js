// Copyright (c) 2025, atul and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sales Session', {
    onload: function (frm) {
        // Add default customers if new or no customer exists
        if ((frm.doc.__islocal && !frm.doc.amended_from) || (!frm.doc.customer.length || !frm.doc.customer[0].customer)) {
            frm.clear_table("customer");
            let customer_seats = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth"];
            customer_seats.forEach(seat => {
                let child = frm.add_child("customer");
                child.seat = seat;
            });
            frm.refresh_field("customer");
        }
        // Disable adding rows
        frm.get_field('customer').grid.cannot_add_rows = true;

        // Prevent deletion by overriding the grid delete function
        frm.fields_dict.customer.grid.wrapper.on('click', '.grid-remove-rows', function () {
            frappe.msgprint(__('Deleting rows is not allowed.'));
        });
    },

    validate: function (frm) {
        // Validate duplicate customers and remove empty rows
        let customers = [];
        let rows_to_remove = [];
        
        frm.doc.customer.forEach((row, idx) => {
            if (row.customer) {
                if (customers.includes(row.customer)) {
                    frappe.throw(__('Duplicate customer: {0}', [row.customer]));
                }
                customers.push(row.customer);
            } else {
                // Mark empty rows for removal
                rows_to_remove.push(idx);
            }
        });

        // Remove empty rows
        rows_to_remove.reverse().forEach(idx => {
            frm.get_field('customer').grid.grid_rows[idx].remove();
        });

        frm.refresh_field("customer");
    },
});


frappe.ui.form.on('Sales Session Item',{
	item_code: async function(frm, cdt, cdn) {	
		let data = locals[cdt][cdn]
		let actual_qty = 0

		if (data.uom == data.stock_uom) {
			frappe.model.set_value(cdt,cdn,'conversion_factor',1)
			frappe.model.set_value(cdt, cdn, 'actual_qty', parseInt(actual_qty)/i.conversion_factor)
		} else {
			await frappe.call({
				method:"shreerakhi_customizations.shree.doctype.sales_session.sales_session.get_uom",
				args:{"item_code":data.item_code},
				callback:function(r){
					for (let i of r.message) {
						if(i.uom == data.uom) {
							frappe.model.set_value(cdt, cdn, 'conversion_factor', i.conversion_factor)
							frappe.model.set_value(cdt, cdn, 'actual_qty', parseInt(actual_qty)/i.conversion_factor)
						}
					}
				}
			})
		}
		frm.refresh_field("items")
		frm.refresh_field("customer")
	}
})


// Avaliable stock in given warehouse
frappe.ui.form.on('Sales Session Item', {
    item_code: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_code) {
            // Fetch the in-hand quantity of the selected item
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Bin',
                    filters: {
                        item_code: row.item_code,
                        warehouse: frm.doc.source_warehouse, // Adjust warehouse as per your requirement
                    },
                    fieldname: 'actual_qty'
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'actual_qty', r.message.actual_qty);
                    } else {
                        frappe.model.set_value(cdt, cdn, 'actual_qty', 0);
                    }
                }
            });
        }
    }
});

// if sales uom is missing then set the stock uom 
frappe.ui.form.on('Sales Session Item', {
    first_order_qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn]; // Access the child table row

        if (!row.uom) {
            frappe.db.get_value('Item', { "item_code": row.item_code }, 'stock_uom')
                .then(result => {
                    if (result.message) {
                        frappe.model.set_value(cdt, cdn, 'uom', result.message.stock_uom); // Update the UOM field
                    }
                });
        }
    }
});	


frappe.ui.form.on('Sales Session Item', {
    item_code: function(frm, cdt, cdn) {
        // Get the current row
        let row = locals[cdt][cdn];

        // Fetch the price list rate for the item
        frappe.db.get_value('Item Price', {"item_code": row.item_code, "uom": row.uom}, 'price_list_rate')
            .then(result => {
                if (result.message) {
                    let rate = result.message.price_list_rate || 0;
                    frappe.model.set_value(cdt, cdn, 'rate', rate);
                }
            });
    }
});

frappe.ui.form.on('Sales Session', {
    refresh: function (frm) {
        calculate_totals(frm);
        calculate_total_amount(frm);
    },
    validate: function (frm) {
        calculate_totals(frm);
        calculate_total_amount(frm);
    },
});

frappe.ui.form.on('Sales Session Item', {
    first_order_qty: calculate_on_qty_change,
    second_order_qty: calculate_on_qty_change,
    third_order_qty: calculate_on_qty_change,
    fourth_order_qty: calculate_on_qty_change,
    fifth_order_qty: calculate_on_qty_change,
    sixth_order_qty: calculate_on_qty_change,
});

function calculate_on_qty_change(frm, cdt, cdn) {
    calculate_totals(frm);
    calculate_total_amount(frm);
}

function calculate_totals(frm) {
    const totals = {
        first_order_quantity: 0,
        second_order_quantity: 0,
        third_order_quantity: 0,
        fourth_order_quantity: 0,
        fifth_order_quantity: 0,
        sixth_order_quantity: 0,
    };

    if (frm.doc.items) {
        for (const row of frm.doc.items) {
            totals.first_order_quantity += row.first_order_qty || 0;
            totals.second_order_quantity += row.second_order_qty || 0;
            totals.third_order_quantity += row.third_order_qty || 0;
            totals.fourth_order_quantity += row.fourth_order_qty || 0;
            totals.fifth_order_quantity += row.fifth_order_qty || 0;
            totals.sixth_order_quantity += row.sixth_order_qty || 0;
        }
    }

    frm.set_value(totals);
}

function calculate_total_amount(frm) {
    if (!frm.doc.items) return;

    const grand_totals = {
        total_ordered_qty: 0,
        first_order_amount: 0,
        second_order_amount: 0,
        third_order_amount: 0,
        fourth_order_amount: 0,
        fifth_order_amount: 0,
        sixth_order_amount: 0,
    };

    for (const row of frm.doc.items) {
        const calculateAmount = qty => (qty || 0) * (row.rate || 0);

        row.first_order_amount = calculateAmount(row.first_order_qty);
        row.second_order_amount = calculateAmount(row.second_order_qty);
        row.third_order_amount = calculateAmount(row.third_order_qty);
        row.fourth_order_amount = calculateAmount(row.fourth_order_qty);
        row.fifth_order_amount = calculateAmount(row.fifth_order_qty);
        row.sixth_order_amount = calculateAmount(row.sixth_order_qty);

        row.stock_uom_rate = row.rate ? row.rate / (row.conversion_factor || 1) : 0;

        const total_qty = [
            row.first_order_qty,
            row.second_order_qty,
            row.third_order_qty,
            row.fourth_order_qty,
            row.fifth_order_qty,
            row.sixth_order_qty,
        ].reduce((acc, qty) => acc + (qty || 0), 0);

        row.ordered_qty = total_qty;

        // Update grand totals
        grand_totals.total_ordered_qty += total_qty;
        grand_totals.first_order_amount += row.first_order_amount;
        grand_totals.second_order_amount += row.second_order_amount;
        grand_totals.third_order_amount += row.third_order_amount;
        grand_totals.fourth_order_amount += row.fourth_order_amount;
        grand_totals.fifth_order_amount += row.fifth_order_amount;
        grand_totals.sixth_order_amount += row.sixth_order_amount;
    }

    frm.set_value(grand_totals);
    frm.refresh_field("items"); // Ensure child table is updated
}

