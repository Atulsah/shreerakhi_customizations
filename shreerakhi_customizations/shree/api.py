"""
PRODUCTION-READY Image Matcher
Best accuracy with multiple fallback methods
Path: shreerakhi_customizations/shree/api.py
"""

import frappe
import hashlib
import requests
from PIL import Image
from io import BytesIO
import imagehash  # pip install imagehash

@frappe.whitelist()
def match_item_by_image(image_url):
    """
    Production-ready image matching with high accuracy
    """
    try:
        # Load uploaded image
        uploaded_img = load_image_from_url(image_url)
        if not uploaded_img:
            return {"success": False, "message": "Failed to load uploaded image"}
        
        # Get all items with images
        items = frappe.get_all(
            "Item",
            filters={"image": ["!=", ""], "disabled": 0},
            fields=["name", "item_code", "item_name", "image", "item_group"]
        )
        
        if not items:
            return {"success": False, "message": "No items with images found"}
        
        matches = []
        
        for item in items:
            try:
                # Load item image
                item_img = load_image_from_url(item.image)
                if not item_img:
                    continue
                
                # Calculate similarity using advanced hashing
                similarity = calculate_advanced_similarity(uploaded_img, item_img)
                
                # Log for debugging
                if similarity > 30:
                    frappe.logger().info(f"Item: {item.item_code}, Similarity: {similarity}%")
                
                # Accept matches above 60%
                if similarity >= 60:
                    # Get warehouse-wise stock
                    warehouse_stock = get_item_warehouses(item.item_code)
                    total_stock = sum(w.get('actual_qty', 0) for w in warehouse_stock)
                    
                    # Format warehouse details
                    warehouse_details = []
                    for wh in warehouse_stock:
                        warehouse_details.append({
                            "warehouse": wh.get('warehouse'),
                            "qty": wh.get('actual_qty', 0),
                            "reserved": wh.get('reserved_qty', 0),
                            "available": wh.get('actual_qty', 0) - wh.get('reserved_qty', 0)
                        })
                    
                    matches.append({
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "item_group": item.item_group or "",
                        "match_percentage": round(similarity, 1),
                        "stock_qty": total_stock,
                        "image": item.image,
                        "warehouse": get_default_warehouse(),
                        "warehouse_stock": warehouse_details  # Added detailed stock
                    })
                    
            except Exception as e:
                frappe.log_error(f"Error processing item {item.get('item_code')}: {str(e)}")
                continue
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x["match_percentage"], reverse=True)
        
        return {
            "success": True,
            "matches": matches[:20],
            "total_items_checked": len(items)
        }
        
    except Exception as e:
        frappe.log_error(f"Image matching error: {str(e)}")
        return {"success": False, "message": str(e)}


def load_image_from_url(url):
    """Load image from URL (local or external)"""
    try:
        if not url:
            return None
        
        # External URL
        if url.startswith("http://") or url.startswith("https://"):
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0'
            })
            if response.status_code != 200:
                return None
            img_data = response.content
        else:
            # Local file
            if "/files/" in url:
                url = "/files/" + url.split("/files/")[-1]
            file_path = frappe.get_site_path("public", url.lstrip("/"))
            with open(file_path, "rb") as f:
                img_data = f.read()
        
        # Load image
        img = Image.open(BytesIO(img_data))
        
        # Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        return img
        
    except Exception as e:
        frappe.log_error(f"Image load error: {str(e)}")
        return None


def calculate_advanced_similarity(img1, img2):
    """
    Advanced similarity using imagehash library
    Returns 0-100 percentage
    """
    try:
        # Method 1: Average Hash (aHash) - 30% weight
        ahash1 = imagehash.average_hash(img1, hash_size=16)
        ahash2 = imagehash.average_hash(img2, hash_size=16)
        ahash_diff = ahash1 - ahash2  # Hamming distance
        ahash_similarity = max(0, 100 - (ahash_diff * 100 / 256))
        
        # Method 2: Perceptual Hash (pHash) - 35% weight - MOST IMPORTANT
        phash1 = imagehash.phash(img1, hash_size=16)
        phash2 = imagehash.phash(img2, hash_size=16)
        phash_diff = phash1 - phash2
        phash_similarity = max(0, 100 - (phash_diff * 100 / 256))
        
        # Method 3: Difference Hash (dHash) - 25% weight
        dhash1 = imagehash.dhash(img1, hash_size=16)
        dhash2 = imagehash.dhash(img2, hash_size=16)
        dhash_diff = dhash1 - dhash2
        dhash_similarity = max(0, 100 - (dhash_diff * 100 / 256))
        
        # Method 4: Wavelet Hash (wHash) - 10% weight
        try:
            whash1 = imagehash.whash(img1)
            whash2 = imagehash.whash(img2)
            whash_diff = whash1 - whash2
            whash_similarity = max(0, 100 - (whash_diff * 100 / 64))
        except:
            whash_similarity = 0
        
        # Weighted average
        final_score = (
            ahash_similarity * 0.30 +
            phash_similarity * 0.35 +
            dhash_similarity * 0.25 +
            whash_similarity * 0.10
        )
        
        # Bonus: If all methods agree highly, boost score
        if ahash_similarity > 90 and phash_similarity > 90 and dhash_similarity > 90:
            final_score = min(100, final_score + 5)
        
        return round(final_score, 2)
        
    except Exception as e:
        frappe.log_error(f"Similarity calculation error: {str(e)}")
        return 0


def get_total_stock(item_code):
    """Get total stock"""
    try:
        stock_data = frappe.db.sql("""
            SELECT SUM(actual_qty) as total_qty
            FROM `tabBin`
            WHERE item_code = %s
        """, (item_code,), as_dict=1)
        
        if stock_data and stock_data[0].total_qty:
            return stock_data[0].total_qty
        return 0
    except:
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
    """Get warehouses with stock"""
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
    except:
        return []


@frappe.whitelist()
def test_single_match(uploaded_url, item_code):
    """Test matching between uploaded image and specific item"""
    try:
        # Get item
        item = frappe.get_doc("Item", item_code)
        
        if not item.image:
            return {"success": False, "message": "Item has no image"}
        
        # Load images
        uploaded_img = load_image_from_url(uploaded_url)
        item_img = load_image_from_url(item.image)
        
        if not uploaded_img or not item_img:
            return {"success": False, "message": "Failed to load images"}
        
        # Calculate similarity
        similarity = calculate_advanced_similarity(uploaded_img, item_img)
        
        # Get detailed hash values for debugging
        ahash1 = str(imagehash.average_hash(uploaded_img, hash_size=16))
        ahash2 = str(imagehash.average_hash(item_img, hash_size=16))
        
        phash1 = str(imagehash.phash(uploaded_img, hash_size=16))
        phash2 = str(imagehash.phash(item_img, hash_size=16))
        
        return {
            "success": True,
            "similarity": similarity,
            "item_code": item_code,
            "item_name": item.item_name,
            "uploaded_image": uploaded_url,
            "item_image": item.image,
            "debug": {
                "ahash_uploaded": ahash1,
                "ahash_item": ahash2,
                "phash_uploaded": phash1,
                "phash_item": phash2
            }
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}