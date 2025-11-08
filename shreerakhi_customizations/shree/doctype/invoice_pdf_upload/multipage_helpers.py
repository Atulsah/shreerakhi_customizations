####   MultipageInvoiceHelper   ####


import frappe
from frappe import _

class MultipageInvoiceHelper:
    """Helper class for handling multipage invoice scenarios"""
    
    @staticmethod
    def detect_page_breaks(items):
        """
        Detect if items list has page break indicators
        Common patterns:
        - Item code like "PAGE-2", "P2", "Continued..."
        - Subtotal rows between pages
        """
        page_breaks = []
        
        for idx, item in enumerate(items):
            item_code = str(item.get("item_code", "")).upper()
            item_name = str(item.get("item_name", "")).upper()
            
            # Check for page break indicators
            if any(keyword in item_code + item_name for keyword in [
                "PAGE", "CONTINUED", "SUBTOTAL", "CARRIED FORWARD",
                "BROUGHT FORWARD", "C/F", "B/F"
            ]):
                page_breaks.append(idx)
        
        return page_breaks
    
    @staticmethod
    def remove_subtotal_rows(items):
        """
        Remove subtotal/page total rows from items
        These are common in multipage invoices but shouldn't be added as items
        """
        filtered_items = []
        
        for item in items:
            item_name = str(item.get("item_name", "")).upper()
            
            # Skip if it's a subtotal row
            if any(keyword in item_name for keyword in [
                "SUBTOTAL", "PAGE TOTAL", "SUB-TOTAL", 
                "CARRIED FORWARD", "BROUGHT FORWARD",
                "TOTAL CARRIED", "TOTAL BROUGHT"
            ]):
                continue
            
            # Skip if item_code is empty but amount exists (likely a total row)
            if not item.get("item_code") and item.get("amount", 0) > 0:
                continue
            
            filtered_items.append(item)
        
        return filtered_items
    
    @staticmethod
    def merge_split_items(items):
        """
        Merge items that were split across pages
        Sometimes same item appears on multiple pages with continuation
        """
        merged_items = {}
        
        for item in items:
            item_code = item.get("item_code")
            
            if not item_code:
                continue
            
            # If item already exists, add quantities
            if item_code in merged_items:
                existing = merged_items[item_code]
                existing["qty"] += item.get("qty", 0)
                existing["amount"] += item.get("amount", 0)
            else:
                merged_items[item_code] = item.copy()
        
        return list(merged_items.values())
    
    @staticmethod
    def validate_page_continuity(extracted_data):
        """
        Validate that all pages were processed
        Check page numbers if available
        """
        page_count = extracted_data.get("page_count", 1)
        
        # Check if we have reasonable number of items for page count
        items_count = len(extracted_data.get("items", []))
        
        # Typical invoice has 10-50 items per page
        expected_min_items = max(1, (page_count - 1) * 5)  # At least 5 items per additional page
        
        if items_count < expected_min_items:
            frappe.msgprint(
                f"Warning: Found only {items_count} items across {page_count} pages. "
                f"Some pages might not have been processed correctly.",
                indicator="orange"
            )
            return False
        
        return True
    
    @staticmethod
    def calculate_expected_total(items, tax_amount=0):
        """
        Calculate expected total from items and tax
        Useful for validation in multipage invoices
        """
        items_subtotal = sum(item.get("amount", 0) for item in items)
        expected_total = items_subtotal + tax_amount
        
        return {
            "subtotal": items_subtotal,
            "tax": tax_amount,
            "total": expected_total
        }


# Add this method to InvoicePDFUpload class

def process_multipage_invoice(self, extracted_data):
    """
    Post-process extracted data for multipage invoices
    Call this after extraction to clean up common multipage issues
    """
    helper = MultipageInvoiceHelper()
    
    # Step 1: Detect and log page breaks
    page_breaks = helper.detect_page_breaks(extracted_data.get("items", []))
    if page_breaks:
        frappe.logger().info(f"Detected page breaks at indices: {page_breaks}")
    
    # Step 2: Remove subtotal rows
    original_count = len(extracted_data.get("items", []))
    extracted_data["items"] = helper.remove_subtotal_rows(extracted_data["items"])
    removed = original_count - len(extracted_data["items"])
    if removed > 0:
        frappe.msgprint(f"Removed {removed} subtotal/page break rows", indicator="blue")
    
    # Step 3: Merge split items (optional - enable if needed)
    # extracted_data["items"] = helper.merge_split_items(extracted_data["items"])
    
    # Step 4: Validate page continuity
    helper.validate_page_continuity(extracted_data)
    
    # Step 5: Validate totals
    calculation = helper.calculate_expected_total(
        extracted_data["items"],
        extracted_data.get("tax_amount", 0)
    )
    
    declared_total = extracted_data.get("total_amount", 0)
    
    if abs(calculation["total"] - declared_total) > 1:  # Allow ₹1 difference for rounding
        frappe.msgprint(
            f"Total mismatch: Calculated ₹{calculation['total']:.2f}, "
            f"Declared ₹{declared_total:.2f}",
            indicator="orange"
        )
        
        # Store calculation for reference
        extracted_data["_calculated_totals"] = calculation
    
    return extracted_data


# Server Script for bulk processing multipage invoices

@frappe.whitelist()
def process_multipage_pdf_folder(folder_path, auto_create=True):
    """
    Process multiple multipage invoice PDFs from a folder
    Useful for bulk upload scenarios
    """
    import os
    
    if not os.path.exists(folder_path):
        frappe.throw(f"Folder not found: {folder_path}")
    
    results = []
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    frappe.publish_realtime(
        "bulk_processing_started",
        {"total": len(pdf_files)},
        user=frappe.session.user
    )
    
    for idx, filename in enumerate(pdf_files):
        try:
            # Create Invoice PDF Upload doc
            doc = frappe.new_doc("Invoice PDF Upload")
            
            # Attach file
            file_path = os.path.join(folder_path, filename)
            
            with open(file_path, 'rb') as f:
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": filename,
                    "content": f.read(),
                    "is_private": 1
                })
                file_doc.insert()
            
            doc.pdf_file = file_doc.file_url
            doc.auto_create_invoice = auto_create
            doc.save()
            
            # Progress update
            frappe.publish_realtime(
                "bulk_processing_progress",
                {
                    "processed": idx + 1,
                    "total": len(pdf_files),
                    "current_file": filename,
                    "status": "success"
                },
                user=frappe.session.user
            )
            
            results.append({
                "file": filename,
                "status": "Success",
                "invoice": doc.sales_invoice,
                "items_count": len(doc.get("items", []))
            })
            
        except Exception as e:
            frappe.log_error(f"Bulk processing error for {filename}: {str(e)}")
            
            results.append({
                "file": filename,
                "status": "Failed",
                "error": str(e)
            })
            
            frappe.publish_realtime(
                "bulk_processing_progress",
                {
                    "processed": idx + 1,
                    "total": len(pdf_files),
                    "current_file": filename,
                    "status": "failed",
                    "error": str(e)
                },
                user=frappe.session.user
            )
    
    frappe.publish_realtime(
        "bulk_processing_completed",
        {"results": results},
        user=frappe.session.user
    )
    
    return results