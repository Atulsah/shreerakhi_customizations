/*frappe.query_reports["Customer Item Catalogue"] = {
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

*/

frappe.query_reports["Customer Item Catalogue"] = {
    filters: [
        {
            fieldname: "price_list",
            label: __("Price List"),
            fieldtype: "Link",
            options: "Price List",
            default: "Standard Selling"
        },
        {
            fieldname: "item_group_filter",
            label: __("Item Group Filter"),
            fieldtype: "Link",
            options: "Item Group",
            default: ""
        },
        {
            fieldname: "min_qty",
            label: __("Minimum Available Qty"),
            fieldtype: "Int",
            default: 0
        },
        {
            fieldname: "item_categories",
            label: __("Item Categories"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_list('Item Category', {
                    fields: ['name'],
                    filters: {
                        name: ['like', '%' + txt + '%']
                    },
                    order_by: 'name'
                }).then(r => {
                    return r.map(d => d.name);
                });
            }
        }
    ],
    
    onload: function(report) {
        report.page.add_inner_button(__("Download Catalogue PDF"), function() {
            let filters = report.get_values();
            
            // Prepare item_categories parameter
            let categories = filters.item_categories || [];
            let categoriesParam = "";
            
            // Handle both array and string formats
            if (categories) {
                let categoriesArray = [];
                
                if (Array.isArray(categories)) {
                    // Already an array from MultiSelectList
                    categoriesArray = categories.filter(c => c);
                } else if (typeof categories === 'string' && categories.trim()) {
                    // Fallback: comma-separated string
                    categoriesArray = categories.split(',').map(c => c.trim()).filter(c => c);
                }
                
                if (categoriesArray.length > 0) {
                    categoriesParam = "&item_categories=" + encodeURIComponent(JSON.stringify(categoriesArray));
                }
            }

            // Build URL - only include parameters that have values
            let url_params = [];
            
            url_params.push("price_list=" + encodeURIComponent(filters.price_list || "Standard Selling"));
            
            if (filters.item_group_filter) {
                url_params.push("item_group_filter=" + encodeURIComponent(filters.item_group_filter));
            }
            
            if (filters.min_qty && filters.min_qty > 0) {
                url_params.push("min_qty=" + filters.min_qty);
            }
            
            if (categoriesParam) {
                url_params.push(categoriesParam.substring(1)); // Remove leading &
            }

            // Direct download with all filters
            window.open(
                frappe.urllib.get_full_url(
                    "/api/method/shreerakhi_customizations.shree.report.customer_item_catalogue.customer_item_catalogue.download_customer_catalogue"
                    + "?" + url_params.join("&")
                )
            );
        });
    }
};