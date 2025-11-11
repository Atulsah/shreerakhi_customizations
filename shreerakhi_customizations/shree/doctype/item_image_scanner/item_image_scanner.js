// Item Image Scanner Client Script
// Path: item_image_scanner/item_image_scanner.js

frappe.ui.form.on('Item Image Scanner', {
    refresh: function(frm) {
        // Scan button functionality
        frm.fields_dict['scan_button'].$input.on('click', function() {
            if (!frm.doc.scan_image) {
                frappe.msgprint(__('Pehle image upload karein'));
                return;
            }
            scan_and_match_items(frm);
        });
        
        // Camera button
        add_camera_button(frm);
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
    frappe.show_progress(__('Scanning'), 30, 100, __('Items match ho rahi hain...'));
    
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
                
                frappe.show_alert({
                    message: __(`${matches.length} items match hui (${r.message.total_items_checked} mein se)`),
                    indicator: 'green'
                }, 5);
            } else {
                frappe.msgprint({
                    title: __('Koi Match Nahi'),
                    message: r.message ? r.message.message : __('Koi matching items nahi mile'),
                    indicator: 'orange'
                });
            }
        },
        error: function(err) {
            frappe.hide_progress();
            console.error('Scan error:', err);
            
            // Better error message
            let error_msg = 'Scanning mein problem aayi. ';
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
            '<div class="alert alert-warning">Koi matching items nahi mile. Different image try karein.</div>'
        );
        return;
    }
    
    let html = '<div class="row" style="margin-top: 15px;">';
    
    matches.forEach(function(match, idx) {
        let stock_class = match.stock_qty > 0 ? 'success' : 'danger';
        let stock_text = match.stock_qty > 0 ? `${match.stock_qty} In Stock` : 'Out of Stock';
        let match_class = match.match_percentage > 70 ? 'success' : 
                         match.match_percentage > 50 ? 'warning' : 'info';
        
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
                                <strong>Stock:</strong> 
                                <span class="badge badge-${stock_class}" style="font-size: 11px;">
                                    ${stock_text}
                                </span>
                            </div>
                            ${match.item_group ? `<div style="margin-bottom: 5px;"><strong>Group:</strong> ${match.item_group}</div>` : ''}
                            ${match.warehouse ? `<div style="margin-bottom: 5px;"><strong>Warehouse:</strong> ${match.warehouse}</div>` : ''}
                        </div>
                        
                        <button class="btn btn-sm btn-primary" 
                                style="width: 100%; margin-top: 10px;"
                                onclick="open_item('${match.item_code}')">
                            <i class="fa fa-external-link"></i> View Item
                        </button>
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
        row.warehouse = match.warehouse;
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
            <i class="fa fa-camera"></i> Camera se Photo Lo
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
        title: __('Camera se Photo'),
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
                                <i class="fa fa-camera"></i> Photo Lo
                            </button>
                            <button class="btn btn-default" id="switch-camera" style="margin-left: 10px;">
                                <i class="fa fa-refresh"></i> Camera Switch
                            </button>
                        </div>
                        <p class="text-muted" style="margin-top: 10px;">
                            Item ko camera ke samne rakhein
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
                frappe.msgprint(__('Camera access nahi mila. Browser settings check karein.'));
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