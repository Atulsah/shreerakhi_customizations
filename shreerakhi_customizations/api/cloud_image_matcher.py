"""
Frappe Cloud Compatible Image Matcher
Server Script mein paste karein (API type)
No external dependencies required
"""

import frappe
import base64
import hashlib
from urllib.parse import urljoin

@frappe.whitelist()
def match_item_by_image(image_url):
    """
    Image matching without PIL/OpenCV
    Pure Python approach using image properties
    """
    try:
        # Get uploaded image data
        uploaded_data = get_image_data(image_url)
        if not uploaded_data:
            return {"success": False, "message": "Image load nahi hua"}
        
        # Fetch all items with images
        items = frappe.get_all(
            "Item",
            filters={"image": ["!=", ""], "disabled": 0},
            fields=["name", "item_code", "item_name", "image", "item_group"]
        )
        
        if not items:
            return {"success": False, "message": "Koi items with images nahi hain"}
        
        matches = []
        
        for item in items:
            try:
                # Get item image data
                item_data = get_image_data(item.image)
                if not item_data:
                    continue
                
                # Calculate similarity
                similarity = calculate_basic_similarity(uploaded_data, item_data)
                
                # Threshold: 40% se zyada match
                if similarity > 40:
                    # Get stock
                    stock_qty = get_total_stock(item.item_code)
                    
                    matches.append({
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "item_group": item.item_group or "",
                        "match_percentage": round(similarity, 2),
                        "stock_qty": stock_qty,
                        "image": item.image,
                        "warehouse": get_default_warehouse()
                    })
                    
            except Exception as e:
                frappe.log_error(f"Item {item.get('item_code', 'unknown')} error: {str(e)}")
                continue
        
        # Sort by similarity
        matches.sort(key=lambda x: x["match_percentage"], reverse=True)
        
        return {
            "success": True,
            "matches": matches[:15],  # Top 15 matches
            "total_items_checked": len(items)
        }
        
    except Exception as e:
        frappe.log_error(f"Image matching main error: {str(e)}")
        return {"success": False, "message": str(e)}


def get_image_data(url):
    """
    Get image file data from URL
    Works with Frappe file system
    """
    try:
        if not url:
            return None
            
        # Remove site URL if present
        if url.startswith("http"):
            url = url.split("/files/")[-1]
            url = "/files/" + url
        
        # Get file from Frappe
        file_doc = frappe.get_all(
            "File",
            filters={"file_url": url},
            fields=["name", "file_url", "file_size"],
            limit=1
        )
        
        if not file_doc:
            # Try direct file read
            file_path = frappe.get_site_path("public", url.lstrip("/"))
            with open(file_path, "rb") as f:
                return f.read()
        
        # Read file content
        file_path = frappe.get_site_path("public", url.lstrip("/"))
        with open(file_path, "rb") as f:
            return f.read()
            
    except Exception as e:
        frappe.log_error(f"Image data read error for {url}: {str(e)}")
        return None


def calculate_basic_similarity(data1, data2):
    """
    Basic similarity without image libraries
    Uses file size, hash, and byte patterns
    """
    try:
        if not data1 or not data2:
            return 0
        
        # 1. File size comparison (weight: 20%)
        size1 = len(data1)
        size2 = len(data2)
        size_diff = abs(size1 - size2)
        size_similarity = max(0, 100 - (size_diff / max(size1, size2) * 100))
        
        # 2. Hash similarity (weight: 30%)
        hash1 = hashlib.md5(data1).hexdigest()
        hash2 = hashlib.md5(data2).hexdigest()
        hash_similarity = 100 if hash1 == hash2 else calculate_hash_similarity(hash1, hash2)
        
        # 3. Byte pattern similarity (weight: 50%)
        # Sample bytes at intervals
        pattern_similarity = calculate_pattern_similarity(data1, data2)
        
        # Weighted average
        final_score = (
            size_similarity * 0.2 +
            hash_similarity * 0.3 +
            pattern_similarity * 0.5
        )
        
        return final_score
        
    except Exception as e:
        frappe.log_error(f"Similarity calculation error: {str(e)}")
        return 0


def calculate_hash_similarity(hash1, hash2):
    """Compare two hashes character by character"""
    matches = sum(c1 == c2 for c1, c2 in zip(hash1, hash2))
    return (matches / len(hash1)) * 100


def calculate_pattern_similarity(data1, data2):
    """
    Compare byte patterns at regular intervals
    Simulates basic image comparison
    """
    try:
        # Sample 100 points from each file
        sample_size = min(len(data1), len(data2), 100)
        interval1 = len(data1) // sample_size
        interval2 = len(data2) // sample_size
        
        samples1 = [data1[i * interval1] for i in range(sample_size)]
        samples2 = [data2[i * interval2] for i in range(sample_size)]
        
        # Calculate difference
        total_diff = sum(abs(s1 - s2) for s1, s2 in zip(samples1, samples2))
        max_diff = sample_size * 255  # Max possible difference
        
        similarity = max(0, 100 - (total_diff / max_diff * 100))
        return similarity
        
    except Exception as e:
        return 50  # Default moderate similarity


def get_total_stock(item_code):
    """Get total stock across all warehouses"""
    try:
        stock_data = frappe.db.sql("""
            SELECT SUM(actual_qty) as total_qty
            FROM `tabBin`
            WHERE item_code = %s
        """, (item_code,), as_dict=1)
        
        if stock_data and stock_data[0].total_qty:
            return stock_data[0].total_qty
        return 0
        
    except Exception as e:
        frappe.log_error(f"Stock fetch error: {str(e)}")
        return 0


def get_default_warehouse():
    """Get default warehouse"""
    try:
        warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
        if not warehouse:
            warehouses = frappe.get_all("Warehouse", limit=1)
            if warehouses:
                warehouse = warehouses[0].name
        return warehouse or "Main Warehouse"
    except:
        return "Main Warehouse"


@frappe.whitelist()
def get_item_warehouses(item_code):
    """Get all warehouses with stock for an item"""
    try:
        warehouses = frappe.db.sql("""
            SELECT 
                warehouse,
                actual_qty,
                reserved_qty,
                projected_qty
            FROM `tabBin`
            WHERE item_code = %s AND actual_qty > 0
            ORDER BY actual_qty DESC
        """, (item_code,), as_dict=1)
        
        return warehouses
        
    except Exception as e:
        frappe.log_error(f"Warehouse fetch error: {str(e)}")
        return []