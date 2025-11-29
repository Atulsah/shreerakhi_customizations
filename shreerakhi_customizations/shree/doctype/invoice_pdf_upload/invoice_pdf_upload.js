// Copyright (c) 2025, atul and contributors
// For license information, please see license.txt

// Client Script for Invoice PDF Upload DocType - Simplified Version

frappe.ui.form.on('Invoice PDF Upload', {
    onload: function(frm) {
        // Load available invoice series on form load
        load_invoice_series(frm);
    },
    
    refresh: function(frm) {
        // API Key Test Button (System Manager only)
        if (frappe.user.has_role('System Manager')) {
            frm.add_custom_button(__('Test API Key'), function() {
                frappe.call({
                    method: 'verify_gemini_api_key',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('Testing Gemini API...'),
                    callback: function(r) {
                        if (r.message) {
                            if (r.message.success) {
                                frappe.msgprint({
                                    title: __('Success'),
                                    message: r.message.message + '<br><br>' +
                                            '<strong>Endpoint:</strong> ' + (r.message.endpoint || 'N/A') + '<br>' +
                                            '<strong>Model:</strong> ' + (r.message.model || 'N/A'),
                                    indicator: 'green'
                                });
                            } else {
                                frappe.msgprint({
                                    title: __('Failed'),
                                    message: r.message.message + '<br><br>' +
                                            (r.message.suggestion || ''),
                                    indicator: 'red'
                                });
                            }
                        }
                    }
                });
            }, __('Actions'));
        }
        
        // Show statistics for multipage invoices
        if (frm.doc.page_count && frm.doc.page_count > 1) {
            frm.dashboard.add_indicator(
                __('Multipage Invoice: {0} pages', [frm.doc.page_count]), 
                'blue'
            );
        }
        
        // Preview button - only if PDF uploaded and invoice not created yet
        if (frm.doc.pdf_file && !frm.doc.sales_invoice) {
            frm.add_custom_button(__('Preview Extracted Data'), function() {
                preview_pdf_data(frm);
            }).addClass('btn-primary');
        }
        
        // View invoice button
        if (frm.doc.sales_invoice) {
            frm.add_custom_button(__('View Sales Invoice'), function() {
                frappe.set_route('Form', 'Sales Invoice', frm.doc.sales_invoice);
            });
        }
        
        // Status indicators
        if (frm.doc.invoice_status === 'Processed') {
            let items_count = 0;
            if (frm.doc.extracted_data) {
                try {
                    items_count = JSON.parse(frm.doc.extracted_data).items.length;
                } catch(e) {
                    items_count = 0;
                }
            }
            frm.dashboard.set_headline_alert(
                __('Invoice created successfully with {0} items', [items_count]), 
                'green'
            );
        } else if (frm.doc.invoice_status === 'Failed') {
            frm.dashboard.set_headline_alert(
                __('Extraction failed. Check error log below.'), 
                'red'
            );
        }
        
        // Show selected series info
        if (frm.doc.invoice_series) {
            update_series_info(frm);
        }
    },
    
    pdf_file: function(frm) {
        if (frm.doc.pdf_file) {
            frm.set_value('invoice_status', 'Pending');
        }
    },
    
    is_multipage: function(frm) {
        // Show/hide multipage settings
        frm.refresh_field('page_count');
        frm.refresh_field('remove_subtotals');
        frm.refresh_field('merge_split_items');
    },
    
    invoice_series: function(frm) {
        // When series is changed, show info
        if (frm.doc.invoice_series) {
            update_series_info(frm);
        } else {
            clear_series_info(frm);
        }
    }
});

// Load available invoice series from Sales Invoice naming series
function load_invoice_series(frm) {
    // Get naming series from Sales Invoice DocType
    frappe.model.with_doctype('Sales Invoice', function() {
        let naming_series = frappe.meta.get_docfield('Sales Invoice', 'naming_series');
        
        if (naming_series && naming_series.options) {
            let series_list = naming_series.options.split('\n').filter(s => s.trim());
            
            if (series_list.length > 0) {
                const series_field = frm.get_field('invoice_series');
                series_field.df.options = series_list.join('\n');
                series_field.refresh();
                
                frappe.show_alert({
                    message: __('Loaded {0} invoice series', [series_list.length]),
                    indicator: 'blue'
                }, 3);
            }
        }
    });
}

// Update series information display
function update_series_info(frm) {
    const html_content = `
        <div class="alert alert-info" style="margin: 10px 0; padding: 15px;">
            <h5 style="margin-top: 0; color: #2490ef;">
                <i class="fa fa-info-circle"></i> Selected Series Information
            </h5>
            <div style="font-size: 13px;">
                <p style="margin: 5px 0;">
                    <strong>📋 Selected Series:</strong> 
                    <code style="background: #f5f5f5; padding: 3px 8px; border-radius: 3px; font-size: 14px;">
                        ${frm.doc.invoice_series}
                    </code>
                </p>
                <p style="margin: 5px 0; color: #666;">
                    <strong>ℹ️ Note:</strong> System will automatically use the next available number in this series.
                </p>
                <p style="margin: 5px 0; color: #28a745;">
                    <strong>✅ Auto-numbering:</strong> Invoice number will be generated automatically based on series sequence.
                </p>
            </div>
        </div>
    `;
    
    frm.get_field('last_invoice_info').$wrapper.html(html_content);
}

// Clear series info
function clear_series_info(frm) {
    frm.get_field('last_invoice_info').$wrapper.html(
        '<div class="text-muted" style="padding: 10px;">Select a series to create invoice with auto-numbering</div>'
    );
}

// Preview extracted PDF data
function preview_pdf_data(frm) {
    frappe.call({
        method: 'preview_extracted_data',
        doc: frm.doc,
        freeze: true,
        freeze_message: __('Processing PDF (may take time for multipage)...'),
        callback: function(r) {
            if (r.message) {
                show_extraction_preview(frm, r.message);
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Extraction Failed'),
                message: __('Could not extract data from PDF. Check error log.'),
                indicator: 'red'
            });
        }
    });
}

// Helper function to show extraction preview
function show_extraction_preview(frm, data) {
    let items_html = '';
    
    if (data.items && data.items.length > 0) {
        // Determine if Bill of Supply or Normal Invoice
        const is_bos = data.invoice_type === 'bill_of_supply';
        
        items_html = '<table class="table table-bordered" style="margin-top: 10px; font-size: 12px;">';
        
        if (is_bos) {
            // Bill of Supply table
            items_html += `<thead style="background: #f8f9fa;">
                <tr>
                    <th>Item Code</th>
                    <th>Box (Qty)</th>
                    <th>Packing (CF)</th>
                    <th>Stock UOM</th>
                    <th>Stock Qty</th>
                    <th>Stock Rate</th>
                    <th>Amount</th>
                </tr>
            </thead><tbody>`;
            
            data.items.forEach(item => {
                items_html += `<tr>
                    <td>${item.item_code || '-'}</td>
                    <td style="text-align: right;">${item.qty || 0}</td>
                    <td style="text-align: right;">${item.conversion_factor || 1}</td>
                    <td>${item.stock_uom || 'Nos'}</td>
                    <td style="text-align: right;">${item.stock_qty || 0}</td>
                    <td style="text-align: right;">₹${(item.stock_rate || 0).toFixed(2)}</td>
                    <td style="text-align: right;"><strong>₹${(item.amount || 0).toFixed(2)}</strong></td>
                </tr>`;
            });
        } else {
            // Normal Invoice table
            items_html += `<thead style="background: #f8f9fa;">
                <tr>
                    <th>Item Code</th>
                    <th>Item Name</th>
                    <th>Qty</th>
                    <th>Rate</th>
                    <th>Amount</th>
                </tr>
            </thead><tbody>`;
            
            data.items.forEach(item => {
                items_html += `<tr>
                    <td>${item.item_code || '-'}</td>
                    <td>${item.item_name || '-'}</td>
                    <td style="text-align: right;">${item.qty || 0}</td>
                    <td style="text-align: right;">₹${(item.rate || 0).toFixed(2)}</td>
                    <td style="text-align: right;"><strong>₹${(item.amount || 0).toFixed(2)}</strong></td>
                </tr>`;
            });
        }
        
        items_html += '</tbody></table>';
    }
    
    // Prepare discount info
    let discount_html = '';
    if (data.discount_percent || data.discount_amount) {
        discount_html = `
            <div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-left: 3px solid #ffc107;">
                ${data.discount_percent ? `<p style="margin: 0;"><strong>Discount:</strong> ${data.discount_percent}%</p>` : ''}
                ${data.discount_amount ? `<p style="margin: 0;"><strong>Discount Amount:</strong> ₹${data.discount_amount.toFixed(2)}</p>` : ''}
            </div>
        `;
    }
    
    let d = new frappe.ui.Dialog({
        title: __('📄 Extracted Data Preview'),
        size: 'extra-large',
        fields: [
            {
                fieldname: 'info',
                fieldtype: 'HTML',
                options: `
                    <div class="row" style="margin-bottom: 15px;">
                        <div class="col-md-6">
                            <h5 style="margin-top: 0; color: #2490ef;">Invoice Information</h5>
                            <p><strong>Customer:</strong> ${data.customer_name || 'Not found'}</p>
                            <p><strong>Date:</strong> ${data.invoice_date || 'Not found'}</p>
                            <p><strong>Invoice Type:</strong> <span class="indicator ${data.invoice_type === 'bill_of_supply' ? 'blue' : 'green'}">${data.invoice_type === 'bill_of_supply' ? 'Bill of Supply' : 'Normal Invoice'}</span></p>
                            ${data.page_count ? `<p><strong>Pages Processed:</strong> <span class="badge">${data.page_count}</span></p>` : ''}
                        </div>
                        <div class="col-md-6">
                            <h5 style="margin-top: 0; color: #28a745;">Totals</h5>
                            <p><strong>Items Count:</strong> ${data.items ? data.items.length : 0}</p>
                            <p><strong>Subtotal:</strong> ₹${(data.total_amount || 0).toFixed(2)}</p>
                            ${data.tax_amount ? `<p><strong>Tax Amount:</strong> ₹${data.tax_amount.toFixed(2)}</p>` : ''}
                        </div>
                    </div>
                    ${discount_html}
                    ${data.notes ? `<div class="alert alert-info" style="margin-top: 10px;">${data.notes}</div>` : ''}
                    <h5 style="margin-top: 15px; border-bottom: 2px solid #d1d8dd; padding-bottom: 5px;">Items List</h5>
                    ${items_html}
                `
            },
            {
                fieldname: 'raw_json',
                fieldtype: 'Code',
                options: 'JSON',
                label: 'Raw JSON Data',
                read_only: 1
            }
        ],
        primary_action_label: __('✅ Create Invoice'),
        primary_action(values) {
            // Check if series is selected
            if (!frm.doc.invoice_series) {
                frappe.msgprint({
                    title: __('Missing Information'),
                    message: __('Please select Invoice Series before creating invoice.'),
                    indicator: 'orange'
                });
                return;
            }
            
            frm.set_value('auto_create_invoice', 1);
            frm.save().then(() => {
                d.hide();
                frappe.show_alert({
                    message: __('✅ Invoice creation started with auto-numbering...'),
                    indicator: 'blue'
                }, 3);
            });
        }
    });
    
    d.set_value('raw_json', JSON.stringify(data, null, 2));
    d.show();
}