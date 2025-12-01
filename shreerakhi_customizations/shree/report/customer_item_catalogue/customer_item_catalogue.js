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
            
            // Check if report has data
            if (!report.data || report.data.length === 0) {
                frappe.msgprint({
                    title: __('No Data'),
                    indicator: 'red',
                    message: __('Please run the report first to see items.')
                });
                return;
            }
            
            // Show item selection dialog
            show_item_selection_dialog(report, filters);
        });
        
        function show_item_selection_dialog(report, filters) {
            // Prepare items list with details
            let items_html = `
                <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <button class="btn btn-xs btn-primary" id="select-all-items">Select All</button>
                        <button class="btn btn-xs btn-default" id="deselect-all-items">Deselect All</button>
                    </div>
                    <span style="font-weight: bold;" id="selected-count">
                        Selected: ${report.data.length} of ${report.data.length}
                    </span>
                </div>
                <div style="max-height: 500px; overflow-y: auto; border: 1px solid #d1d8dd; padding: 10px; background: #fafbfc;">
            `;
            
            report.data.forEach(function(row, index) {
                // Get image URL
                let image_url = '';
                if (row.image) {
                    // Extract image URL from the HTML anchor tag
                    let temp_div = document.createElement('div');
                    temp_div.innerHTML = row.image_link;
                    let anchor = temp_div.querySelector('a');
                    image_url = anchor ? anchor.href : '';
                }
                
                items_html += `
                    <div style="padding: 10px; border-bottom: 1px solid #e8e8e8; background: white; margin-bottom: 8px; border-radius: 4px;">
                        <label style="margin: 0; cursor: pointer; display: flex; align-items: center; gap: 12px;">
                            <input type="checkbox" 
                                   class="item-checkbox" 
                                   data-item-code="${row.item_code}"
                                   data-index="${index}"
                                   checked
                                   style="margin: 0; flex-shrink: 0;">
                            
                            ${image_url ? `
                                <img src="${image_url}" 
                                     style="width: 60px; height: 60px; object-fit: cover; border: 1px solid #ddd; border-radius: 4px; flex-shrink: 0;"
                                     onerror="this.style.display='none'">
                            ` : `
                                <div style="width: 60px; height: 60px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 10px; color: #999;">
                                    No Image
                                </div>
                            `}
                            
                            <div style="flex: 1; min-width: 0;">
                                <div style="font-weight: 600; font-size: 14px; color: #2c3e50; margin-bottom: 4px;">
                                    ${row.item_code}
                                </div>
                                <div style="font-size: 13px; color: #5a5a5a; margin-bottom: 2px;">
                                    ${row.item_name || 'N/A'}
                                </div>
                                ${row.item_group ? `
                                    <div style="font-size: 12px; color: #8D99A6;">
                                        <i class="fa fa-folder-o"></i> ${row.item_group}
                                    </div>
                                ` : ''}
                            </div>
                            
                            <div style="text-align: right; flex-shrink: 0; padding-left: 10px;">
                                <div style="font-size: 13px; color: #666; margin-bottom: 4px;">
                                    Available Qty
                                </div>
                                <div style="font-size: 18px; font-weight: bold; color: ${row.available_qty > 0 ? '#27ae60' : '#e74c3c'};">
                                    ${row.available_qty !== undefined ? row.available_qty : 'N/A'}
                                </div>
                                ${row.stock_uom ? `
                                    <div style="font-size: 11px; color: #999;">
                                        ${row.stock_uom}
                                    </div>
                                ` : ''}
                            </div>
                        </label>
                    </div>
                `;
            });
            
            items_html += '</div>';
            
            // Create dialog
            let d = new frappe.ui.Dialog({
                title: __('Select Items for Catalogue'),
                fields: [
                    {
                        fieldtype: 'HTML',
                        fieldname: 'items_list',
                        options: items_html
                    }
                ],
                primary_action_label: __('Download PDF'),
                primary_action: function() {
                    // Get selected items
                    let selected_items = [];
                    d.$wrapper.find('.item-checkbox:checked').each(function() {
                        selected_items.push($(this).data('item-code'));
                    });
                    
                    if (selected_items.length === 0) {
                        frappe.msgprint({
                            title: __('No Items Selected'),
                            indicator: 'orange',
                            message: __('Please select at least one item.')
                        });
                        return;
                    }
                    
                    // Close dialog and download
                    d.hide();
                    download_catalogue(filters, selected_items);
                }
            });
            
            d.show();
            
            // Update counter function
            function update_counter() {
                let total = d.$wrapper.find('.item-checkbox').length;
                let checked = d.$wrapper.find('.item-checkbox:checked').length;
                d.$wrapper.find('#selected-count').text(`Selected: ${checked} of ${total}`);
            }
            
            // Select All button
            d.$wrapper.find('#select-all-items').on('click', function() {
                d.$wrapper.find('.item-checkbox').prop('checked', true);
                update_counter();
            });
            
            // Deselect All button
            d.$wrapper.find('#deselect-all-items').on('click', function() {
                d.$wrapper.find('.item-checkbox').prop('checked', false);
                update_counter();
            });
            
            // Individual checkbox change
            d.$wrapper.find('.item-checkbox').on('change', function() {
                update_counter();
            });
        }
        
        function download_catalogue(filters, selected_items) {
            // Prepare item_categories parameter
            let categories = filters.item_categories || [];
            let categoriesParam = "";
            
            if (categories) {
                let categoriesArray = [];
                
                if (Array.isArray(categories)) {
                    categoriesArray = categories.filter(c => c);
                } else if (typeof categories === 'string' && categories.trim()) {
                    categoriesArray = categories.split(',').map(c => c.trim()).filter(c => c);
                }
                
                if (categoriesArray.length > 0) {
                    categoriesParam = "&item_categories=" + encodeURIComponent(JSON.stringify(categoriesArray));
                }
            }

            // Build URL
            let url_params = [];
            
            url_params.push("price_list=" + encodeURIComponent(filters.price_list || "Standard Selling"));
            
            if (filters.item_group_filter) {
                url_params.push("item_group_filter=" + encodeURIComponent(filters.item_group_filter));
            }
            
            if (filters.min_qty && filters.min_qty > 0) {
                url_params.push("min_qty=" + filters.min_qty);
            }
            
            if (categoriesParam) {
                url_params.push(categoriesParam.substring(1));
            }
            
            // Add selected items
            if (selected_items && selected_items.length > 0) {
                url_params.push("selected_items=" + encodeURIComponent(JSON.stringify(selected_items)));
            }

            // Show loading message
            frappe.show_alert({
                message: __('Generating PDF with {0} items...', [selected_items.length]),
                indicator: 'blue'
            }, 5);

            // Download
            window.open(
                frappe.urllib.get_full_url(
                    "/api/method/shreerakhi_customizations.shree.report.customer_item_catalogue.customer_item_catalogue.download_customer_catalogue"
                    + "?" + url_params.join("&")
                )
            );
        }
    }
};