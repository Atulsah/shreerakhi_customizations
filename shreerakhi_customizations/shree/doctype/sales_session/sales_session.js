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

        // Disable adding/deleting rows manually
        frm.get_field('customer').grid.cannot_add_rows = true;
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
                rows_to_remove.push(idx);
            }
        });

        // Remove empty rows
        rows_to_remove.reverse().forEach(idx => {
            frm.get_field('customer').grid.grid_rows[idx].remove();
        });

        frm.refresh_field("customer");
    },

    refresh: function (frm) {
        calculate_totals(frm);
        calculate_total_amount(frm);
    }
});

// ===========================================================================
// SALES SESSION ITEM HANDLERS
// ===========================================================================

frappe.ui.form.on('Sales Session Item', {
    // Handle UOM conversion and stock fetching
    item_code: async function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.item_code) return;

        // -------------------------------------------------------------
        // 1️⃣ Fetch and set conversion factor if needed
        // -------------------------------------------------------------
        if (row.uom && row.uom !== row.stock_uom) {
            await frappe.call({
                method: "shreerakhi_customizations.shree.doctype.sales_session.sales_session.get_uom",
                args: { "item_code": row.item_code },
                callback: function (r) {
                    if (r.message) {
                        for (let i of r.message) {
                            if (i.uom === row.uom) {
                                frappe.model.set_value(cdt, cdn, 'conversion_factor', i.conversion_factor);
                                break;
                            }
                        }
                    }
                }
            });
        } else {
            frappe.model.set_value(cdt, cdn, 'conversion_factor', 1);
        }

        // -------------------------------------------------------------
        // 2️⃣ Fetch actual quantity from selected warehouse
        // -------------------------------------------------------------
        if (frm.doc.source_warehouse) {
            let r = await frappe.db.get_value('Bin', {
                item_code: row.item_code,
                warehouse: frm.doc.source_warehouse
            }, 'actual_qty');

            frappe.model.set_value(cdt, cdn, 'actual_qty', r.message?.actual_qty || 0);
        }

        // -------------------------------------------------------------
        // 3️⃣ Fetch rate from Sales UOM; fallback to Stock UOM
        // -------------------------------------------------------------
        let rate = 0;
        let res = await frappe.db.get_value('Item Price', {
            item_code: row.item_code,
            uom: row.uom
        }, 'price_list_rate');

        if (res.message?.price_list_rate) {
            rate = res.message.price_list_rate;
        } else {
            // fallback to stock uom rate
            let stock = await frappe.db.get_value('Item', {
                item_code: row.item_code
            }, 'stock_uom');

            if (stock.message?.stock_uom) {
                let stock_rate = await frappe.db.get_value('Item Price', {
                    item_code: row.item_code,
                    uom: stock.message.stock_uom
                }, 'price_list_rate');

                if (stock_rate.message?.price_list_rate) {
                    let conversion = row.conversion_factor || 1;
                    rate = stock_rate.message.price_list_rate * conversion;
                }
            }
        }

        frappe.model.set_value(cdt, cdn, 'rate', rate);
        frm.refresh_field("items");
    },

    // Set stock UOM if missing when entering qty
    first_order_qty: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.uom && row.item_code) {
            frappe.db.get_value('Item', { item_code: row.item_code }, 'stock_uom').then(r => {
                if (r.message?.stock_uom) {
                    frappe.model.set_value(cdt, cdn, 'uom', r.message.stock_uom);
                }
            });
        }
        calculate_on_qty_change(frm, cdt, cdn);
    },

    // Recalculate whenever any qty changes
    second_order_qty: calculate_on_qty_change,
    third_order_qty: calculate_on_qty_change,
    fourth_order_qty: calculate_on_qty_change,
    fifth_order_qty: calculate_on_qty_change,
    sixth_order_qty: calculate_on_qty_change,

    // If user changes UOM manually, refetch rate
    uom: function (frm, cdt, cdn) {
        frm.script_manager.trigger('item_code', cdt, cdn);
    },

    // Update rate if conversion factor manually changed
    conversion_factor: async function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.item_code) return;

        let stock = await frappe.db.get_value('Item', { item_code: row.item_code }, 'stock_uom');
        if (stock.message?.stock_uom && stock.message.stock_uom !== row.uom) {
            let stock_rate = await frappe.db.get_value('Item Price', {
                item_code: row.item_code,
                uom: stock.message.stock_uom
            }, 'price_list_rate');

            if (stock_rate.message?.price_list_rate) {
                let rate = stock_rate.message.price_list_rate * (row.conversion_factor || 1);
                frappe.model.set_value(cdt, cdn, 'rate', rate);
            }
        }
    }
});

// ===========================================================================
// TOTAL CALCULATION FUNCTIONS
// ===========================================================================

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
        const calcAmt = qty => (qty || 0) * (row.rate || 0);

        row.first_order_amount = calcAmt(row.first_order_qty);
        row.second_order_amount = calcAmt(row.second_order_qty);
        row.third_order_amount = calcAmt(row.third_order_qty);
        row.fourth_order_amount = calcAmt(row.fourth_order_qty);
        row.fifth_order_amount = calcAmt(row.fifth_order_qty);
        row.sixth_order_amount = calcAmt(row.sixth_order_qty);

        row.stock_uom_rate = row.rate ? row.rate / (row.conversion_factor || 1) : 0;

        const total_qty = [
            row.first_order_qty,
            row.second_order_qty,
            row.third_order_qty,
            row.fourth_order_qty,
            row.fifth_order_qty,
            row.sixth_order_qty,
        ].reduce((a, b) => a + (b || 0), 0);

        row.ordered_qty = total_qty;

        grand_totals.total_ordered_qty += total_qty;
        grand_totals.first_order_amount += row.first_order_amount;
        grand_totals.second_order_amount += row.second_order_amount;
        grand_totals.third_order_amount += row.third_order_amount;
        grand_totals.fourth_order_amount += row.fourth_order_amount;
        grand_totals.fifth_order_amount += row.fifth_order_amount;
        grand_totals.sixth_order_amount += row.sixth_order_amount;
    }

    frm.set_value(grand_totals);
    frm.refresh_field("items");
}
