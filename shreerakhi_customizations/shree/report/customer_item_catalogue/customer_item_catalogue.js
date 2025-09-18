frappe.query_reports["Customer Item Catalogue"] = {
    onload: function(report) {
        report.page.add_inner_button(__("Download Catalogue PDF"), function() {
            let filters = report.get_values();

            // Direct download (no base64 / popup issue)
            window.open(
                frappe.urllib.get_full_url(
                    "/api/method/shreerakhi_customizations.shree.report.customer_item_catalogue.customer_item_catalogue.download_customer_catalogue"
                    + "?price_list=" + (filters.price_list || "Standard Selling")
                )
            );
        });
    }
};
