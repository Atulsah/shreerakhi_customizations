// Copyright (c) 2025, atul and contributors
// For license information, please see license.txt

// Client Script for Invoice PDF Upload DocType - Multipage Support

frappe.ui.form.on('Invoice PDF Upload', {
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
        
        // Preview button
        if (frm.doc.pdf_file && !frm.doc.sales_invoice) {
            frm.add_custom_button(__('Preview Extracted Data'), function() {
                frappe.call({
                    method: 'preview_extracted_data',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('Processing multipage PDF...'),
                    callback: function(r) {
                        if (r.message) {
                            show_extraction_preview(frm, r.message);
                        }
                    }
                });
            }).addClass('btn-primary');
        }
        
        // View invoice button
        if (frm.doc.sales_invoice) {
            frm.add_custom_button(__('View Sales Invoice'), function() {
                frappe.set_route('Form', 'Sales Invoice', frm.doc.sales_invoice);
            });
        }
        
        // Bulk upload button (only for System Manager)
        if (frappe.user.has_role('System Manager')) {
            frm.add_custom_button(__('Bulk Upload'), function() {
                show_bulk_upload_dialog();
            }, __('Actions'));
        }
        
        // Status indicators
        if (frm.doc.invoice_status === 'Processed') {
            frm.dashboard.set_headline_alert(
                __('Invoice created successfully with {0} items', 
                [frm.doc.extracted_data ? JSON.parse(frm.doc.extracted_data).items.length : 0]), 
                'green'
            );
        } else if (frm.doc.invoice_status === 'Failed') {
            frm.dashboard.set_headline_alert(
                __('Extraction failed. Check error log below.'), 
                'red'
            );
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
    }
});

// Helper function to show extraction preview
function show_extraction_preview(frm, data) {
    let items_html = '';
    
    if (data.items && data.items.length > 0) {
        items_html = '<table class="table table-bordered" style="margin-top: 10px;">';
        items_html += '<thead><tr><th>Item Code</th><th>Item Name</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead>';
        items_html += '<tbody>';
        
        data.items.forEach(item => {
            items_html += `<tr>
                <td>${item.item_code || '-'}</td>
                <td>${item.item_name || '-'}</td>
                <td>${item.qty || 0}</td>
                <td>₹${(item.rate || 0).toFixed(2)}</td>
                <td>₹${(item.amount || 0).toFixed(2)}</td>
            </tr>`;
        });
        
        items_html += '</tbody></table>';
    }
    
    let d = new frappe.ui.Dialog({
        title: __('Extracted Data Preview'),
        size: 'extra-large',
        fields: [
            {
                fieldname: 'info',
                fieldtype: 'HTML',
                options: `
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Customer:</strong> ${data.customer_name || 'Not found'}</p>
                            <p><strong>Date:</strong> ${data.invoice_date || 'Not found'}</p>
                            ${data.page_count ? `<p><strong>Pages Processed:</strong> ${data.page_count}</p>` : ''}
                        </div>
                        <div class="col-md-6">
                            <p><strong>Items Count:</strong> ${data.items ? data.items.length : 0}</p>
                            <p><strong>Total Amount:</strong> ₹${(data.total_amount || 0).toFixed(2)}</p>
                            <p><strong>Tax Amount:</strong> ₹${(data.tax_amount || 0).toFixed(2)}</p>
                        </div>
                    </div>
                    ${data.notes ? `<div class="alert alert-info">${data.notes}</div>` : ''}
                    <h5 style="margin-top: 15px;">Items List</h5>
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
        primary_action_label: __('Create Invoice'),
        primary_action(values) {
            frm.set_value('auto_create_invoice', 1);
            frm.save().then(() => {
                d.hide();
                frappe.show_alert({
                    message: __('Invoice creation started...'),
                    indicator: 'blue'
                });
            });
        }
    });
    
    d.set_value('raw_json', JSON.stringify(data, null, 2));
    d.show();
}

// Bulk upload dialog
function show_bulk_upload_dialog() {
    frappe.prompt([
        {
            fieldname: 'folder_path',
            fieldtype: 'Data',
            label: 'Server Folder Path',
            reqd: 1,
            description: 'Full path to folder containing PDF files on server'
        },
        {
            fieldname: 'auto_create',
            fieldtype: 'Check',
            label: 'Auto Create Invoices',
            default: 1
        }
    ], function(values) {
        frappe.call({
            method: 'invoice_extractor.invoice_extractor.doctype.invoice_pdf_upload.invoice_pdf_upload.process_multipage_pdf_folder',
            args: values,
            freeze: true,
            freeze_message: __('Processing bulk upload...'),
            callback: function(r) {
                if (r.message) {
                    show_bulk_results(r.message);
                }
            }
        });
    }, __('Bulk Upload PDFs'), __('Start Processing'));
}

// Show bulk processing results
function show_bulk_results(results) {
    let success = results.filter(r => r.status === 'Success').length;
    let failed = results.filter(r => r.status === 'Failed').length;
    
    let html = `
        <div class="alert alert-info">
            <strong>Processing Complete</strong><br>
            Success: ${success} | Failed: ${failed}
        </div>
        <table class="table table-bordered">
            <thead>
                <tr><th>File</th><th>Status</th><th>Invoice</th><th>Items</th></tr>
            </thead>
            <tbody>
    `;
    
    results.forEach(r => {
        html += `<tr>
            <td>${r.file}</td>
            <td><span class="indicator ${r.status === 'Success' ? 'green' : 'red'}">${r.status}</span></td>
            <td>${r.invoice || '-'}</td>
            <td>${r.items_count || '-'}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    
    frappe.msgprint({
        title: __('Bulk Processing Results'),
        message: html,
        indicator: success > failed ? 'green' : 'orange',
        wide: true
    });
}