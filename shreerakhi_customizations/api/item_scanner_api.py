import frappe
from PIL import Image
import io
import base64
import requests
from urllib.parse import urljoin

@frappe.whitelist()
def match_item_by_image(image_url):
    """
    Image se items ko match karne ka function
    Simple approach using image comparison
    """
    try:
        # Uploaded image load karein
        uploaded_image = load_image_from_url(image_url)
        if not uploaded_image:
            return {"success": False, "message": "Image load nahi hua"}
        
        # Sabhi items fetch karein jo image ke saath hain
        items = frappe.get_all(
            "Item",
            filters={"image": ["!=", ""]},
            fields=["name", "item_code", "item_name", "image"]
        )
        
        matches = []
        
        for item in items:
            try:
                # Item ka image load karein
                item_image = load_image_from_url(item.image)
                if not item_image:
                    continue
                
                # Image similarity check karein (basic method)
                similarity = calculate_image_similarity(uploaded_image, item_image)
                
                if similarity > 30:  # 30% se zyada match
                    # Stock quantity fetch karein
                    stock_qty = get_stock_balance(item.item_code)
                    
                    matches.append({
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "match_percentage": similarity,
                        "stock_qty": stock_qty,
                        "image": item.image,
                        "warehouse": get_default_warehouse()
                    })
            except Exception as e:
                frappe.log_error(f"Item {item.item_code} process error: {str(e)}")
                continue
        
        # Sort by match percentage (highest first)
        matches.sort(key=lambda x: x["match_percentage"], reverse=True)
        
        return {
            "success": True,
            "matches": matches[:10]  # Top 10 matches
        }
        
    except Exception as e:
        frappe.log_error(f"Image matching error: {str(e)}")
        return {"success": False, "message": str(e)}


def load_image_from_url(url):
    """URL se image load karein"""
    try:
        if url.startswith("/"):
            # Local file path
            site_url = frappe.utils.get_url()
            url = urljoin(site_url, url)
        
        response = requests.get(url, timeout=10)
        img = Image.open(io.BytesIO(response.content))
        return img.convert('RGB')
    except Exception as e:
        frappe.log_error(f"Image load error: {str(e)}")
        return None


def calculate_image_similarity(img1, img2):
    """
    Do images ki similarity calculate karein
    Simple histogram-based comparison
    """
    try:
        # Images ko same size banayein
        size = (100, 100)
        img1 = img1.resize(size)
        img2 = img2.resize(size)
        
        # Histogram comparison
        h1 = img1.histogram()
        h2 = img2.histogram()
        
        # Calculate similarity using histogram correlation
        sum_sq = sum((h1[i] - h2[i])**2 for i in range(len(h1)))
        similarity = 100 - (sum_sq / (len(h1) * 10000)) * 100
        
        return max(0, min(100, similarity))  # 0-100 range mein
        
    except Exception as e:
        frappe.log_error(f"Similarity calculation error: {str(e)}")
        return 0


def get_stock_balance(item_code, warehouse=None):
    """Item ka stock balance fetch karein"""
    from erpnext.stock.utils import get_latest_stock_qty
    
    try:
        if not warehouse:
            warehouse = get_default_warehouse()
        
        qty = get_latest_stock_qty(item_code, warehouse)
        return qty or 0
    except:
        return 0


def get_default_warehouse():
    """Default warehouse fetch karein"""
    warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    if not warehouse:
        warehouse = frappe.get_all("Warehouse", limit=1)
        if warehouse:
            warehouse = warehouse[0].name
    return warehouse or ""


@frappe.whitelist()
def get_item_stock_details(item_code):
    """Specific item ki stock details"""
    stock_data = frappe.get_all(
        "Bin",
        filters={"item_code": item_code},
        fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"]
    )
    
    return stock_data