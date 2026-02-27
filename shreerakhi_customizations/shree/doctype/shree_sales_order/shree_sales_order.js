// ─────────────────────────────────────────────────────────
//  Shree Sales Order — Client Script
//  App : shreerakhi_customizations | Module : Shree
// ─────────────────────────────────────────────────────────

frappe.ui.form.on("Shree Sales Order", {

    // ── Form Open ──────────────────────────────────────────
    onload(frm) {
        if (frm.is_new()) {
            frm._loading_customer = true;

            frappe.call({
                method: "shreerakhi_customizations.shree.doctype.shree_sales_order.shree_sales_order.get_customer_details_for_user",
                callback(r) {
                    frm._loading_customer = false;
                    if (!r.message || !r.message.customer) return;

                    const d = r.message;
                    frm.set_value("customer",      d.customer);
                    frm.set_value("customer_name", d.customer_name);

                    if (d.company)
                        frm.set_value("company", d.company);
                    if (d.customer_address) {
                        frm.set_value("customer_address", d.customer_address);
                        frm.set_value("address_display",  d.address_display);
                    }
                    if (d.shipping_address_name) {
                        frm.set_value("shipping_address_name", d.shipping_address_name);
                        frm.set_value("shipping_address",      d.shipping_address);
                    }

                    // Portal user ke liye customer read-only
                    frm.set_df_property("customer", "read_only", 1);
                    frm.refresh_field("customer");
                }
            });
        }

        if (!frm.doc.transaction_date)
            frm.set_value("transaction_date", frappe.datetime.get_today());

        if (!frm.doc.company) {
            frm.set_value("company",
                frappe.defaults.get_default("Company") ||
                frappe.boot.sysdefaults.company
            );
        }
    },

    // ── After Save / Refresh ───────────────────────────────
    refresh(frm) {
        // Submitted ho gaya to ERPNext SO ka link dikhao
        if (frm.doc.erpnext_sales_order && frm.doc.docstatus === 1) {
            frm.add_custom_button(
                `📄 ERPNext SO: ${frm.doc.erpnext_sales_order}`,
                () => frappe.set_route("Form", "Sales Order", frm.doc.erpnext_sales_order),
                "View"
            );
        }

        // Portal user ke liye submit button customize karo
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.page.set_primary_action("Submit Order", () => {
                _confirm_and_submit(frm);
            });
        }
    },

    // ── Customer Change ────────────────────────────────────
    customer(frm) {
        if (!frm.doc.customer || frm._loading_customer) return;

        frappe.call({
            method: "shreerakhi_customizations.shree.doctype.shree_sales_order.shree_sales_order.get_customer_details_for_user",
            callback(r) {
                if (!r.message || r.message.customer !== frm.doc.customer) return;
                const d = r.message;
                if (d.customer_address) {
                    frm.set_value("customer_address", d.customer_address);
                    frm.set_value("address_display",  d.address_display);
                }
                if (d.shipping_address_name) {
                    frm.set_value("shipping_address_name", d.shipping_address_name);
                    frm.set_value("shipping_address",      d.shipping_address);
                }
            }
        });
    },

    // ── Address Change ─────────────────────────────────────
    customer_address(frm) {
        if (!frm.doc.customer_address) return;
        frappe.call({
            method: "frappe.contacts.doctype.address.address.get_address_display",
            args: { address_dict: frm.doc.customer_address },
            callback(r) { if (r.message) frm.set_value("address_display", r.message); }
        });
    },

    shipping_address_name(frm) {
        if (!frm.doc.shipping_address_name) return;
        frappe.call({
            method: "frappe.contacts.doctype.address.address.get_address_display",
            args: { address_dict: frm.doc.shipping_address_name },
            callback(r) { if (r.message) frm.set_value("shipping_address", r.message); }
        });
    }
});


// ─────────────────────────────────────────────────────────
//  Child Table — Shree Sales Order Item
// ─────────────────────────────────────────────────────────

frappe.ui.form.on("Shree Sales Order Item", {

    item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code) return;

        frappe.call({
            method: "shreerakhi_customizations.shree.doctype.shree_sales_order.shree_sales_order.get_item_details",
            args: { item_code: row.item_code },
            callback(r) {
                if (!r.message) return;
                const d = r.message;
                frappe.model.set_value(cdt, cdn, "uom",        d.uom);
                frappe.model.set_value(cdt, cdn, "rate",       d.rate);
                frappe.model.set_value(cdt, cdn, "item_name",  d.item_name);
                frappe.model.set_value(cdt, cdn, "item_image", d.item_image);
                _calc_amount(frm, cdt, cdn);
            }
        });
    },

    qty(frm, cdt, cdn)     { _calc_amount(frm, cdt, cdn); },
    rate(frm, cdt, cdn)    { _calc_amount(frm, cdt, cdn); },
    items_remove(frm)      { _update_totals(frm); }
});


// ─────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────

function _calc_amount(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
    _update_totals(frm);
}

function _update_totals(frm) {
    let grand_total = 0, total_qty = 0;
    (frm.doc.items || []).forEach(r => {
        grand_total += flt(r.amount);
        total_qty   += flt(r.qty);
    });
    frm.set_value("grand_total", grand_total);
    frm.set_value("total_qty",   total_qty);
    frm.refresh_fields(["grand_total", "total_qty"]);
}

function _confirm_and_submit(frm) {
    // Items check
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint({
            title: "Items Zaroori Hain",
            message: "Submit karne se pehle kam se kam ek item add karo.",
            indicator: "red"
        });
        return;
    }

    // Grand total summary banana
    const item_summary = (frm.doc.items || [])
        .map(r => `• ${r.item_name || r.item_code} × ${r.qty} = ₹${flt(r.amount).toFixed(2)}`)
        .join("<br>");

    frappe.confirm(
        `<b>Order Summary:</b><br><br>
        ${item_summary}
        <br><br>
        <b>Grand Total: ₹${flt(frm.doc.grand_total).toFixed(2)}</b>
        <br><br>
        Kya aap yeh order submit karna chahte hain?<br>
        <small style="color:gray">Submit hone par ERPNext mein Sales Order draft ban jayega.</small>`,
        () => {
            // Save first then submit
            frm.save("Submit");
        }
    );
}
