"""
HYBRID Image Matcher - Auto-detects available libraries
Uses imagehash if available, falls back to PIL-only
Path: shreerakhi_customizations/shree/api.py
"""

import frappe
import hashlib
import requests
from PIL import Image
from io import BytesIO

# Try to import imagehash, fallback to None
try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
    frappe.logger().info("✓ imagehash library available - using advanced matching")
except ImportError:
    IMAGEHASH_AVAILABLE = False
    frappe.logger().info("✗ imagehash not available - using PIL-only matching")


@frappe.whitelist()
def match_item_by_image(image_url):
    """
    Hybrid image matching - auto-selects best available method
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
        matching_method = "imagehash" if IMAGEHASH_AVAILABLE else "PIL-only"
        
        for item in items:
            try:
                # Load item image
                item_img = load_image_from_url(item.image)
                if not item_img:
                    continue
                
                # Calculate similarity - auto-select best method
                if IMAGEHASH_AVAILABLE:
                    similarity = calculate_imagehash_similarity(uploaded_img, item_img)
                    threshold = 60  # Higher accuracy, so lower threshold
                else:
                    similarity = calculate_pil_similarity(uploaded_img, item_img)
                    threshold = 65  # PIL-only needs higher threshold
                
                # Log for debugging
                if similarity > 40:
                    frappe.logger().info(f"[{matching_method}] Item: {item.item_code}, Similarity: {similarity}%")
                
                # Accept matches above threshold
                if similarity >= threshold:
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
                        "warehouse_stock": warehouse_details
                    })
                    
            except Exception as e:
                frappe.log_error(f"Error processing item {item.get('item_code')}: {str(e)}")
                continue
        
        # Sort by similarity
        matches.sort(key=lambda x: x["match_percentage"], reverse=True)
        
        return {
            "success": True,
            "matches": matches[:20],
            "total_items_checked": len(items),
            "matching_method": matching_method,
            "imagehash_available": IMAGEHASH_AVAILABLE
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
            response = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
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


# ============================================
# IMAGEHASH METHOD (Best accuracy)
# ============================================
def calculate_imagehash_similarity(img1, img2):
    """
    Advanced similarity using imagehash library
    Only called if imagehash is available
    """
    try:
        # Method 1: Average Hash - 30%
        ahash1 = imagehash.average_hash(img1, hash_size=16)
        ahash2 = imagehash.average_hash(img2, hash_size=16)
        ahash_diff = ahash1 - ahash2
        ahash_sim = max(0, 100 - (ahash_diff * 100 / 256))
        
        # Method 2: Perceptual Hash - 35% (MOST IMPORTANT)
        phash1 = imagehash.phash(img1, hash_size=16)
        phash2 = imagehash.phash(img2, hash_size=16)
        phash_diff = phash1 - phash2
        phash_sim = max(0, 100 - (phash_diff * 100 / 256))
        
        # Method 3: Difference Hash - 25%
        dhash1 = imagehash.dhash(img1, hash_size=16)
        dhash2 = imagehash.dhash(img2, hash_size=16)
        dhash_diff = dhash1 - dhash2
        dhash_sim = max(0, 100 - (dhash_diff * 100 / 256))
        
        # Method 4: Wavelet Hash - 10%
        try:
            whash1 = imagehash.whash(img1)
            whash2 = imagehash.whash(img2)
            whash_diff = whash1 - whash2
            whash_sim = max(0, 100 - (whash_diff * 100 / 64))
        except:
            whash_sim = 0
        
        # Weighted average
        final_score = (
            ahash_sim * 0.30 +
            phash_sim * 0.35 +
            dhash_sim * 0.25 +
            whash_sim * 0.10
        )
        
        # Bonus for high agreement
        if ahash_sim > 90 and phash_sim > 90 and dhash_sim > 90:
            final_score = min(100, final_score + 5)
        
        return round(final_score, 2)
        
    except Exception as e:
        frappe.log_error(f"imagehash similarity error: {str(e)}")
        # Fallback to PIL method if imagehash fails
        return calculate_pil_similarity(img1, img2)


# ============================================
# PIL-ONLY METHOD (Fallback)
# ============================================
def calculate_pil_similarity(img1, img2):
    """
    PIL-only similarity calculation
    Used when imagehash is not available
    """
    try:
        # Method 1: dHash - 35%
        dhash_sim = dhash_similarity(img1, img2, hash_size=16)
        
        # Method 2: aHash - 30%
        ahash_sim = ahash_similarity(img1, img2, hash_size=16)
        
        # Method 3: Histogram - 20%
        hist_sim = histogram_similarity(img1, img2)
        
        # Method 4: Thumbnail - 15%
        thumb_sim = thumbnail_similarity(img1, img2, size=(64, 64))
        
        # Weighted average
        final_score = (
            dhash_sim * 0.35 +
            ahash_sim * 0.30 +
            hist_sim * 0.20 +
            thumb_sim * 0.15
        )
        
        return round(final_score, 2)
        
    except Exception as e:
        frappe.log_error(f"PIL similarity error: {str(e)}")
        return 0


def dhash_similarity(img1, img2, hash_size=16):
    """Difference Hash"""
    try:
        def compute_dhash(image):
            image = image.resize((hash_size + 1, hash_size), Image.LANCZOS)
            image = image.convert('L')
            pixels = list(image.getdata())
            
            diff = []
            for row in range(hash_size):
                for col in range(hash_size):
                    idx_left = row * (hash_size + 1) + col
                    idx_right = row * (hash_size + 1) + col + 1
                    diff.append(1 if pixels[idx_left] > pixels[idx_right] else 0)
            
            return ''.join(str(bit) for bit in diff)
        
        hash1 = compute_dhash(img1)
        hash2 = compute_dhash(img2)
        
        if hash1 == hash2:
            return 100.0
        
        differences = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        similarity = (1 - differences / len(hash1)) * 100
        
        return max(0, similarity)
    except:
        return 0


def ahash_similarity(img1, img2, hash_size=16):
    """Average Hash"""
    try:
        def compute_ahash(image):
            image = image.resize((hash_size, hash_size), Image.LANCZOS)
            image = image.convert('L')
            
            pixels = list(image.getdata())
            avg = sum(pixels) / len(pixels)
            
            bits = ''.join('1' if pixel > avg else '0' for pixel in pixels)
            return bits
        
        hash1 = compute_ahash(img1)
        hash2 = compute_ahash(img2)
        
        if hash1 == hash2:
            return 100.0
        
        differences = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        similarity = (1 - differences / len(hash1)) * 100
        
        return max(0, similarity)
    except:
        return 0


def histogram_similarity(img1, img2):
    """Histogram comparison"""
    try:
        img1 = img1.resize((256, 256), Image.LANCZOS)
        img2 = img2.resize((256, 256), Image.LANCZOS)
        
        h1_r = img1.split()[0].histogram()
        h1_g = img1.split()[1].histogram()
        h1_b = img1.split()[2].histogram()
        
        h2_r = img2.split()[0].histogram()
        h2_g = img2.split()[1].histogram()
        h2_b = img2.split()[2].histogram()
        
        def chi_square(h1, h2):
            chi = 0
            for i in range(len(h1)):
                if h1[i] + h2[i] != 0:
                    chi += ((h1[i] - h2[i]) ** 2) / (h1[i] + h2[i])
            return chi
        
        chi_r = chi_square(h1_r, h2_r)
        chi_g = chi_square(h1_g, h2_g)
        chi_b = chi_square(h1_b, h2_b)
        
        avg_chi = (chi_r + chi_g + chi_b) / 3
        similarity = max(0, 100 - (avg_chi / 500))
        
        return min(100, similarity)
    except:
        return 0


def thumbnail_similarity(img1, img2, size=(64, 64)):
    """Thumbnail pixel comparison"""
    try:
        thumb1 = img1.resize(size, Image.LANCZOS)
        thumb2 = img2.resize(size, Image.LANCZOS)
        
        pixels1 = list(thumb1.getdata())
        pixels2 = list(thumb2.getdata())
        
        mse = 0
        for p1, p2 in zip(pixels1, pixels2):
            for c1, c2 in zip(p1, p2):
                mse += (c1 - c2) ** 2
        
        mse = mse / (len(pixels1) * 3)
        similarity = max(0, 100 - (mse / 650))
        
        return min(100, similarity)
    except:
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


def get_item_warehouses(item_code):
    """Get warehouse-wise stock"""
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
    """Test matching with debug info"""
    try:
        item = frappe.get_doc("Item", item_code)
        
        if not item.image:
            return {"success": False, "message": "Item has no image"}
        
        uploaded_img = load_image_from_url(uploaded_url)
        item_img = load_image_from_url(item.image)
        
        if not uploaded_img or not item_img:
            return {"success": False, "message": "Failed to load images"}
        
        # Calculate using both methods
        if IMAGEHASH_AVAILABLE:
            imagehash_similarity = calculate_imagehash_similarity(uploaded_img, item_img)
        else:
            imagehash_similarity = None
        
        pil_similarity = calculate_pil_similarity(uploaded_img, item_img)
        
        return {
            "success": True,
            "item_code": item_code,
            "item_name": item.item_name,
            "imagehash_available": IMAGEHASH_AVAILABLE,
            "imagehash_similarity": imagehash_similarity,
            "pil_similarity": pil_similarity,
            "used_method": "imagehash" if IMAGEHASH_AVAILABLE else "PIL-only"
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def check_matching_status():
    """Check which matching method is available"""
    return {
        "imagehash_available": IMAGEHASH_AVAILABLE,
        "pil_available": True,
        "active_method": "imagehash (Best)" if IMAGEHASH_AVAILABLE else "PIL-only (Good)",
        "recommendation": "Install imagehash for better accuracy: pip3 install imagehash" if not IMAGEHASH_AVAILABLE else "Using best available method"
    }