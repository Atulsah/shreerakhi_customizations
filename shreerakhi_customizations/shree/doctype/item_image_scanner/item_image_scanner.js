// Item Image Scanner Client Script
// Path: item_image_scanner/item_image_scanner.js

frappe.ui.form.on('Item Image Scanner', {
    refresh: function(frm) {
        // Scan button functionality
        frm.fields_dict['scan_button'].$input.on('click', function() {
            if (!frm.doc.scan_image) {
                frappe.msgprint(__('Please upload an image first'));
                return;
            }
            scan_and_match_items(frm);
        });
        
        // Camera button
        add_camera_button(frm);
        
        // Check matching status
        check_matching_status(frm);
    },
    
    scan_image: function(frm) {
        // Auto scan when image is uploaded
        if (frm.doc.scan_image) {
            setTimeout(function() {
                scan_and_match_items(frm);
            }, 800);
        }
    }
});

function scan_and_match_items(frm) {
    frappe.show_progress(__('Scanning'), 30, 100, __('Matching items...'));
    
    // CORRECT API call path
    frappe.call({
        method: 'shreerakhi_customizations.shree.api.match_item_by_image',
        args: {
            image_url: frm.doc.scan_image
        },
        freeze: true,
        freeze_message: __('Scanning image...'),
        callback: function(r) {
            frappe.hide_progress();
            
            console.log('API Response:', r); // Debug log
            
            if (r.message && r.message.success) {
                let matches = r.message.matches || [];
                display_results(frm, matches);
                populate_child_table(frm, matches);
                
                // Show matching method being used
                let method_indicator = r.message.imagehash_available ? 
                    '<span class="indicator-pill green">Advanced Matching (imagehash)</span>' : 
                    '<span class="indicator-pill orange">Standard Matching (PIL)</span>';
                
                frappe.show_alert({
                    message: __(`${matches.length} items matched (out of ${r.message.total_items_checked}) - ${method_indicator}`),
                    indicator: 'green'
                }, 7);
            } else {
                frappe.msgprint({
                    title: __('No Matches Found'),
                    message: r.message ? r.message.message : __('No matching items found. Try a different image.'),
                    indicator: 'orange'
                });
            }
        },
        error: function(err) {
            frappe.hide_progress();
            console.error('Scan error:', err);
            
            // Better error message
            let error_msg = 'Scanning error occurred. ';
            if (err.message) {
                error_msg += err.message;
            } else {
                error_msg += 'Please check console for details.';
            }
            
            frappe.msgprint({
                title: __('Error'),
                message: __(error_msg),
                indicator: 'red'
            });
        }
    });
}

function display_results(frm, matches) {
    if (!matches || matches.length === 0) {
        frm.fields_dict.matching_results.$wrapper.html(
            '<div class="alert alert-warning">No matching items found. Try a different image.</div>'
        );
        return;
    }
    
    let html = '<div class="row" style="margin-top: 15px;">';
    
    matches.forEach(function(match, idx) {
        let stock_class = match.stock_qty > 0 ? 'success' : 'danger';
        let stock_text = match.stock_qty > 0 ? `${match.stock_qty} In Stock` : 'Out of Stock';
        let match_class = match.match_percentage > 70 ? 'success' : 
                         match.match_percentage > 50 ? 'warning' : 'info';
        
        // Warehouse stock details
        let warehouse_html = '';
        if (match.warehouse_stock && match.warehouse_stock.length > 0) {
            warehouse_html = '<div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee;">';
            warehouse_html += '<strong style="font-size: 11px;">Warehouse Stock:</strong><br>';
            match.warehouse_stock.forEach(function(wh) {
                let wh_badge_class = wh.qty > 0 ? 'success' : 'secondary';
                warehouse_html += `<div style="font-size: 10px; margin-top: 3px;">
                    <span class="badge badge-${wh_badge_class}" style="font-size: 9px;">${wh.warehouse}</span>
                    <span style="color: #666;"> ${wh.qty} qty (Avail: ${wh.available})</span>
                </div>`;
            });
            warehouse_html += '</div>';
        }
        
        html += `
            <div class="col-sm-6 col-md-4 col-lg-3" style="margin-bottom: 20px;">
                <div class="card" style="border: 1px solid #ddd; border-radius: 8px; overflow: hidden; height: 100%;">
                    ${match.image ? 
                        `<img src="${match.image}" class="card-img-top" style="height: 180px; object-fit: cover; cursor: pointer;" 
                         onclick="show_image('${match.image}', '${match.item_name}')">` 
                        : '<div style="height: 180px; background: #f5f5f5; display: flex; align-items: center; justify-content: center;"><i class="fa fa-image fa-3x text-muted"></i></div>'}
                    
                    <div class="card-body" style="padding: 12px;">
                        <h6 class="card-title" style="margin-bottom: 8px; font-weight: 600;">${match.item_name}</h6>
                        
                        <div style="font-size: 12px; color: #666;">
                            <div style="margin-bottom: 5px;">
                                <strong>Code:</strong> <code>${match.item_code}</code>
                            </div>
                            <div style="margin-bottom: 5px;">
                                <strong>Match:</strong> 
                                <span class="badge badge-${match_class}" style="font-size: 11px;">
                                    ${Math.round(match.match_percentage)}%
                                </span>
                            </div>
                            <div style="margin-bottom: 5px;">
                                <strong>Total Stock:</strong> 
                                <span class="badge badge-${stock_class}" style="font-size: 11px;">
                                    ${stock_text}
                                </span>
                            </div>
                            ${match.item_group ? `<div style="margin-bottom: 5px;"><strong>Group:</strong> ${match.item_group}</div>` : ''}
                            ${warehouse_html}
                        </div>
                        
                        <button class="btn btn-sm btn-primary" 
                                style="width: 100%; margin-top: 10px;"
                                onclick="open_item('${match.item_code}')">
                            <i class="fa fa-external-link"></i> View Item
                        </button>
                        ${match.warehouse_stock && match.warehouse_stock.length > 0 ? 
                            `<button class="btn btn-sm btn-default" 
                                    style="width: 100%; margin-top: 5px;"
                                    onclick="show_warehouse_details('${match.item_code}', '${match.item_name}', ${JSON.stringify(match.warehouse_stock).replace(/"/g, '&quot;')})">
                                <i class="fa fa-list"></i> Warehouse Details
                            </button>` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    frm.fields_dict.matching_results.$wrapper.html(html);
}

function populate_child_table(frm, matches) {
    frm.clear_table('matched_items');
    
    matches.forEach(function(match) {
        let row = frm.add_child('matched_items');
        row.item_code = match.item_code;
        row.item_name = match.item_name;
        row.match_percentage = match.match_percentage;
        row.stock_qty = match.stock_qty;
        row.image = match.image;
        
        // Show primary warehouse with most stock
        if (match.warehouse_stock && match.warehouse_stock.length > 0) {
            // Sort by quantity (highest first)
            let sorted_wh = match.warehouse_stock.sort((a, b) => b.qty - a.qty);
            row.warehouse = sorted_wh[0].warehouse;
        } else {
            row.warehouse = match.warehouse;
        }
    });
    
    frm.refresh_field('matched_items');
}

function add_camera_button(frm) {
    // Check if button already exists
    if (frm.fields_dict.scan_image.$wrapper.find('.camera-btn').length) {
        return;
    }
    
    let btn_html = `
        <button class="btn btn-sm btn-default camera-btn" style="margin-top: 8px;">
            <i class="fa fa-camera"></i> Take Photo
        </button>
    `;
    
    let $btn = $(btn_html);
    $btn.on('click', function(e) {
        e.preventDefault();
        open_camera_dialog(frm);
    });
    
    frm.fields_dict.scan_image.$wrapper.append($btn);
}

function open_camera_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Take Photo'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'camera_html',
                options: `
                    <div style="text-align: center;">
                        <video id="video-stream" autoplay playsinline 
                               style="max-width: 100%; max-height: 400px; border: 2px solid #ddd; border-radius: 8px;">
                        </video>
                        <canvas id="photo-canvas" style="display: none;"></canvas>
                        <div style="margin-top: 15px;">
                            <button class="btn btn-primary btn-lg" id="capture-photo">
                                <i class="fa fa-camera"></i> Capture
                            </button>
                            <button class="btn btn-default" id="switch-camera" style="margin-left: 10px;">
                                <i class="fa fa-refresh"></i> Switch Camera
                            </button>
                        </div>
                        <p class="text-muted" style="margin-top: 10px;">
                            Position the item in front of camera
                        </p>
                    </div>
                `
            }
        ]
    });
    
    d.show();
    
    // Camera logic
    let video = null;
    let stream = null;
    let facingMode = 'environment'; // Back camera (mobile)
    
    setTimeout(function() {
        video = document.getElementById('video-stream');
        let canvas = document.getElementById('photo-canvas');
        let captureBtn = document.getElementById('capture-photo');
        let switchBtn = document.getElementById('switch-camera');
        
        function startCamera() {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
            
            navigator.mediaDevices.getUserMedia({
                video: { facingMode: facingMode },
                audio: false
            })
            .then(function(s) {
                stream = s;
                video.srcObject = stream;
            })
            .catch(function(err) {
                console.error('Camera error:', err);
                frappe.msgprint(__('Camera access denied. Please check browser settings.'));
            });
        }
        
        startCamera();
        
        // Switch camera (front/back)
        switchBtn.onclick = function() {
            facingMode = facingMode === 'environment' ? 'user' : 'environment';
            startCamera();
        };
        
        // Capture photo
        captureBtn.onclick = function() {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            
            canvas.toBlob(function(blob) {
                // Stop camera
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                }
                
                // Upload file
                upload_image_file(frm, blob);
                d.hide();
            }, 'image/jpeg', 0.9);
        };
        
        // Cleanup on dialog close
        d.$wrapper.on('hidden.bs.modal', function() {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
        });
        
    }, 500);
}

function upload_image_file(frm, blob) {
    let filename = 'scan_' + Date.now() + '.jpg';
    let file = new File([blob], filename, { type: 'image/jpeg' });
    
    frappe.show_progress(__('Uploading'), 50, 100);
    
    // Upload using FileReader
    let reader = new FileReader();
    reader.onload = function(e) {
        frappe.call({
            method: 'frappe.handler.upload_file',
            args: {
                filename: filename,
                filedata: e.target.result,
                is_private: 0,
                folder: 'Home/Attachments'
            },
            callback: function(r) {
                frappe.hide_progress();
                if (r.message) {
                    frm.set_value('scan_image', r.message.file_url);
                    frappe.show_alert({
                        message: __('Image uploaded successfully!'),
                        indicator: 'green'
                    });
                }
            }
        });
    };
    reader.readAsDataURL(file);
}

// Global functions
window.open_item = function(item_code) {
    frappe.set_route('Form', 'Item', item_code);
};

window.show_image = function(url, title) {
    let d = new frappe.ui.Dialog({
        title: title || 'Item Image',
        size: 'large',
        fields: [{
            fieldtype: 'HTML',
            options: `<img src="${url}" style="max-width: 100%; height: auto;">`
        }]
    });
    d.show();
};

window.show_warehouse_details = function(item_code, item_name, warehouse_stock) {
    // Parse warehouse stock if it's a string
    if (typeof warehouse_stock === 'string') {
        warehouse_stock = JSON.parse(warehouse_stock);
    }
    
    let html = '<table class="table table-bordered" style="margin-top: 10px;">';
    html += '<thead><tr>';
    html += '<th>Warehouse</th>';
    html += '<th>Actual Qty</th>';
    html += '<th>Reserved</th>';
    html += '<th>Available</th>';
    html += '</tr></thead><tbody>';
    
    let total_actual = 0;
    let total_reserved = 0;
    let total_available = 0;
    
    warehouse_stock.forEach(function(wh) {
        total_actual += wh.qty || 0;
        total_reserved += wh.reserved || 0;
        total_available += wh.available || 0;
        
        let row_class = wh.available > 0 ? '' : 'text-muted';
        html += `<tr class="${row_class}">`;
        html += `<td><strong>${wh.warehouse}</strong></td>`;
        html += `<td>${wh.qty || 0}</td>`;
        html += `<td>${wh.reserved || 0}</td>`;
        html += `<td><span class="badge badge-${wh.available > 0 ? 'success' : 'secondary'}">${wh.available || 0}</span></td>`;
        html += '</tr>';
    });
    
    // Total row
    html += '<tr style="font-weight: bold; background-color: #f5f5f5;">';
    html += '<td>TOTAL</td>';
    html += `<td>${total_actual}</td>`;
    html += `<td>${total_reserved}</td>`;
    html += `<td><span class="badge badge-primary">${total_available}</span></td>`;
    html += '</tr>';
    
    html += '</tbody></table>';
    
    let d = new frappe.ui.Dialog({
        title: `Stock Details: ${item_name} (${item_code})`,
        size: 'large',
        fields: [{
            fieldtype: 'HTML',
            options: html
        }],
        primary_action_label: 'View Item',
        primary_action: function() {
            frappe.set_route('Form', 'Item', item_code);
            d.hide();
        }
    });
    d.show();
};