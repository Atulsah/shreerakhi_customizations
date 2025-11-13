"""
IMPROVED Image Matcher with Visual Similarity
Path: shreerakhi_customizations/shree/api.py
Uses PIL for better image comparison
"""

import frappe
import hashlib
import requests
from PIL import Image
from io import BytesIO

@frappe.whitelist()
def match_item_by_image(image_url):
    """
    Image matching with VISUAL similarity (not just bytes)
    """
    try:
        # Get uploaded image
        uploaded_img = load_image_from_url(image_url)
        if not uploaded_img:
            return {"success": False, "message": "Failed to load uploaded image"}
        
        # Fetch all items with images
        items = frappe.get_all(
            "Item",
            filters={"image": ["!=", ""], "disabled": 0},
            fields=["name", "item_code", "item_name", "image", "item_group"]
        )
        
        if not items:
            return {"success": False, "message": "No items match with image"}
        
        matches = []
        checked_count = 0
        
        for item in items:
            try:
                checked_count += 1
                
                # Load item image
                item_img = load_image_from_url(item.image)
                if not item_img:
                    continue
                
                # Calculate VISUAL similarity using multiple methods
                similarity = calculate_visual_similarity(uploaded_img, item_img)
                
                # Log for debugging
                frappe.log_error(f"Item: {item.item_code}, Visual Similarity: {similarity}%")
                
                # If good match (70%+ is good, 50%+ is acceptable)
                if similarity > 50:
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
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x["match_percentage"], reverse=True)
        
        return {
            "success": True,
            "matches": matches[:15],
            "total_items_checked": checked_count,
            "items_with_images": len(items)
        }
        
    except Exception as e:
        frappe.log_error(f"Image matching error: {str(e)}")
        return {"success": False, "message": str(e)}


def load_image_from_url(url):
    """
    Load image from URL and return PIL Image object
    """
    try:
        if not url:
            return None
        
        # Download image (local or external)
        if url.startswith("http://") or url.startswith("https://"):
            response = requests.get(url, timeout=30)
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
        
        # Convert to PIL Image
        img = Image.open(BytesIO(img_data))
        
        # Convert to RGB (remove alpha channel if exists)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        return img
        
    except Exception as e:
        frappe.log_error(f"Image load error for {url}: {str(e)}")
        return None


def calculate_visual_similarity(img1, img2):
    """
    Calculate visual similarity using multiple techniques
    Returns percentage (0-100)
    """
    try:
        # Method 1: Perceptual Hash (pHash) - Most important
        phash_similarity = compare_perceptual_hash(img1, img2)
        
        # Method 2: Average Hash (aHash)
        ahash_similarity = compare_average_hash(img1, img2)
        
        # Method 3: Histogram comparison
        hist_similarity = compare_histograms(img1, img2)
        
        # Method 4: Structural similarity (thumbnail comparison)
        struct_similarity = compare_thumbnails(img1, img2)
        
        # Weighted average (pHash gets highest weight)
        final_score = (
            phash_similarity * 0.40 +  # Most important
            ahash_similarity * 0.25 +
            hist_similarity * 0.20 +
            struct_similarity * 0.15
        )
        
        return round(final_score, 2)
        
    except Exception as e:
        frappe.log_error(f"Visual similarity error: {str(e)}")
        return 0


def compare_perceptual_hash(img1, img2, hash_size=8):
    """
    Perceptual Hash - detects similar images even if resized/compressed
    """
    try:
        def dhash(image):
            """Difference Hash"""
            # Resize to hash_size+1 x hash_size
            image = image.resize((hash_size + 1, hash_size), Image.LANCZOS)
            # Convert to grayscale
            image = image.convert('L')
            
            # Calculate differences
            pixels = list(image.getdata())
            difference = []
            for row in range(hash_size):
                for col in range(hash_size):
                    pixel_left = pixels[row * (hash_size + 1) + col]
                    pixel_right = pixels[row * (hash_size + 1) + col + 1]
                    difference.append(pixel_left > pixel_right)
            
            # Convert to hash
            decimal_value = 0
            hex_string = []
            for index, value in enumerate(difference):
                if value:
                    decimal_value += 2 ** (index % 8)
                if (index % 8) == 7:
                    hex_string.append(hex(decimal_value)[2:].rjust(2, '0'))
                    decimal_value = 0
            
            return ''.join(hex_string)
        
        hash1 = dhash(img1)
        hash2 = dhash(img2)
        
        # Calculate Hamming distance
        if hash1 == hash2:
            return 100.0
        
        # Compare hex strings
        differences = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        similarity = (1 - differences / len(hash1)) * 100
        
        return max(0, similarity)
        
    except Exception as e:
        frappe.log_error(f"Perceptual hash error: {str(e)}")
        return 0


def compare_average_hash(img1, img2, hash_size=8):
    """
    Average Hash - simple but effective
    """
    try:
        def ahash(image):
            # Resize and convert to grayscale
            image = image.resize((hash_size, hash_size), Image.LANCZOS)
            image = image.convert('L')
            
            # Get pixel values
            pixels = list(image.getdata())
            avg = sum(pixels) / len(pixels)
            
            # Create hash based on average
            bits = ''.join('1' if pixel > avg else '0' for pixel in pixels)
            return hex(int(bits, 2))[2:]
        
        hash1 = ahash(img1)
        hash2 = ahash(img2)
        
        if hash1 == hash2:
            return 100.0
        
        # Hamming distance
        differences = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        similarity = (1 - differences / max(len(hash1), len(hash2))) * 100
        
        return max(0, similarity)
        
    except Exception as e:
        return 0


def compare_histograms(img1, img2):
    """
    Compare color histograms - good for similar colored images
    """
    try:
        # Resize for faster processing
        img1 = img1.resize((256, 256), Image.LANCZOS)
        img2 = img2.resize((256, 256), Image.LANCZOS)
        
        # Get histograms for each color channel
        h1_r = img1.split()[0].histogram()
        h1_g = img1.split()[1].histogram()
        h1_b = img1.split()[2].histogram()
        
        h2_r = img2.split()[0].histogram()
        h2_g = img2.split()[1].histogram()
        h2_b = img2.split()[2].histogram()
        
        # Calculate correlation for each channel
        import math
        
        def correlation(hist1, hist2):
            # Normalize
            sum1 = sum(hist1)
            sum2 = sum(hist2)
            if sum1 == 0 or sum2 == 0:
                return 0
            
            hist1_norm = [h / sum1 for h in hist1]
            hist2_norm = [h / sum2 for h in hist2]
            
            # Calculate correlation
            mean1 = sum(hist1_norm) / len(hist1_norm)
            mean2 = sum(hist2_norm) / len(hist2_norm)
            
            numerator = sum((h1 - mean1) * (h2 - mean2) 
                          for h1, h2 in zip(hist1_norm, hist2_norm))
            
            denominator = math.sqrt(
                sum((h1 - mean1) ** 2 for h1 in hist1_norm) *
                sum((h2 - mean2) ** 2 for h2 in hist2_norm)
            )
            
            if denominator == 0:
                return 0
            
            return numerator / denominator
        
        corr_r = correlation(h1_r, h2_r)
        corr_g = correlation(h1_g, h2_g)
        corr_b = correlation(h1_b, h2_b)
        
        # Average correlation
        avg_corr = (corr_r + corr_g + corr_b) / 3
        
        # Convert to percentage (correlation is -1 to 1, we want 0 to 100)
        similarity = (avg_corr + 1) / 2 * 100
        
        return max(0, min(100, similarity))
        
    except Exception as e:
        return 0


def compare_thumbnails(img1, img2, size=(50, 50)):
    """
    Direct pixel comparison of small thumbnails
    """
    try:
        # Resize both to same small size
        thumb1 = img1.resize(size, Image.LANCZOS)
        thumb2 = img2.resize(size, Image.LANCZOS)
        
        # Get pixel data
        pixels1 = list(thumb1.getdata())
        pixels2 = list(thumb2.getdata())
        
        # Calculate pixel difference
        total_diff = 0
        for p1, p2 in zip(pixels1, pixels2):
            # Each pixel is (R, G, B)
            diff = sum(abs(c1 - c2) for c1, c2 in zip(p1, p2))
            total_diff += diff
        
        # Maximum possible difference
        max_diff = len(pixels1) * 3 * 255
        
        # Convert to similarity percentage
        similarity = (1 - total_diff / max_diff) * 100
        
        return max(0, similarity)
        
    except Exception as e:
        return 0


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
    except:
        return []