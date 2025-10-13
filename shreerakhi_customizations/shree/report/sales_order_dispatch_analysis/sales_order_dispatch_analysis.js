// Copyright (c) 2025, atul and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Order Dispatch Analysis"] = {
    filters: [
        {
            fieldname: "warehouse",
            label: __("Warehouse"),
            fieldtype: "Link",
            options: "Warehouse",
            reqd: 1
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "MultiSelectList",
            options: "Customer",
            get_data: function(txt) {
                return frappe.db.get_link_options("Customer", txt);
            }
        },
        {
            fieldname: "status",
            label: __("Sales Order Status"),
            fieldtype: "Select",
            options: ["", "To Deliver and Bill", "To Deliver", "To Bill", "Completed", "Closed"]
        },
    ],

   /* onload: function(report) {
        // Add Color Legend Bar
        if (!report.page.wrapper.find(".color-legend").length) {
            const legend_html = `
                <div class="color-legend" style="
                    display: flex;
                    gap: 20px;
                    align-items: center;
                    background: #f9f9f9;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 8px 16px;
                    margin-bottom: 10px;
                    font-size: 13px;
                    flex-wrap: wrap;
                ">
                    <div><span style="display:inline-block;width:14px;height:14px;background:red;margin-right:6px;border-radius:3px;"></span> Not Ready to Dispatch</div>
                    <div><span style="display:inline-block;width:14px;height:14px;background:orange;margin-right:6px;border-radius:3px;"></span> Partially Ready</div>
                    <div><span style="display:inline-block;width:14px;height:14px;background:green;margin-right:6px;border-radius:3px;"></span> Fully Delivered</div>
                </div>
            `;
            $(legend_html).insertBefore(report.page.wrapper.find(".frappe-control[data-fieldname='warehouse']"));
        }
    },*/

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "color" && data.color) {
            const color = data.color.toLowerCase();
            if (color === "red") value = `<span style="color:red;font-weight:bold;">${data.color}</span>`;
            if (color === "orange") value = `<span style="color:orange;font-weight:bold;">${data.color}</span>`;
            if (color === "green") value = `<span style="color:green;font-weight:bold;">${data.color}</span>`;
        }

        if (column.fieldname === "invoice_button") {
            return `<button class="btn btn-success btn-sm create-invoice" data-so="${data.sales_order}">${__("Create Invoice")}</button>`;
        }

        if (column.fieldname === "select_box") {
            return `<input type="checkbox" class="select-order" data-so="${data.sales_order}">`;
        }

        return value;
    },

    after_datatable_render: function(report) {
        $(".create-invoice").off("click").on("click", function() {
            const so_name = $(this).data("so");
            const warehouse = frappe.query_report.get_filter_value("warehouse");

            if (!warehouse) {
                frappe.msgprint("Please select a warehouse first.");
                return;
            }

            frappe.confirm(
                `Create Draft Sales Invoice for ${so_name} from warehouse ${warehouse}?`,
                function() {
                    frappe.call({
                        method: "shreerakhi_customizations.shree.report.sales_order_dispatch_analysis.sales_order_dispatch_analysis.create_sales_invoice",
                        args: { sales_order: so_name, warehouse: warehouse },
                        callback: function(r) {
                            if (r.message && r.message.name) {
                                frappe.msgprint({
                                    title: "Invoice Created",
                                    message: `<a href="/app/sales-invoice/${r.message.name}" target="_blank">${r.message.name}</a>`,
                                    indicator: "green"
                                });
                            } else {
                                frappe.msgprint({
                                    title: "No Invoice Created",
                                    message: "No items available to invoice for this order.",
                                    indicator: "orange"
                                });
                            }
                            report.refresh();
                        }
                    });
                }
            );
        });
    }
};
