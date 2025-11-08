# Copyright (c) 2024, Atul Sah
# Frappe Cloud Compatible Version - Uses External APIs

import frappe
from frappe.model.document import Document
import json
import requests
import base64
from frappe.utils import get_files_path
import os

class InvoicePDFUpload(Document):
    def validate(self):
        if self.pdf_file and not self.sales_invoice and self.auto_create_invoice:
            self.extract_and_create_invoice()
    
    def extract_and_create_invoice(self):
        """PDF se data extract karke Sales Invoice create karta hai"""
        try:
            # PDF file read karna
            file_doc = frappe.get_doc("File", {"file_url": self.pdf_file})
            
            # API se data extract karna
            extracted_data = self.extract_pdf_using_api(file_doc)
            
            # Extracted data ko JSON field mein store karna
            self.extracted_data = json.dumps(extracted_data, indent=2)
            
            # Set detected invoice type
            if extracted_data.get("invoice_type") == "bill_of_supply":
                self.detected_invoice_type = "Bill of Supply"
            else:
                self.detected_invoice_type = "Normal Invoice"
            
            # Sales Invoice create karna
            if extracted_data and extracted_data.get("customer_name"):
                invoice = self.create_sales_invoice(extracted_data)
                self.sales_invoice = invoice.name
                self.invoice_status = "Processed"
                frappe.msgprint(f"Sales Invoice {invoice.name} successfully created!")
            else:
                self.invoice_status = "Failed"
                frappe.msgprint("Could not extract sufficient data from PDF", indicator="red")
            
        except Exception as e:
            self.invoice_status = "Failed"
            frappe.log_error(f"Error in PDF extraction: {str(e)}", "Invoice PDF Upload Error")
            frappe.throw(f"PDF extraction failed: {str(e)}")
    
    def extract_pdf_using_api(self, file_doc):
        """External API use karke PDF se data extract karna"""
        
        # Check which API to use based on site config
        api_service = frappe.conf.get("pdf_extraction_service", "gemini")
        
        if api_service == "gemini":
            return self.extract_with_gemini(file_doc)
        elif api_service == "openai":
            return self.extract_with_openai(file_doc)
        elif api_service == "azure":
            return self.extract_with_azure(file_doc)
        else:
            frappe.throw("Please configure PDF extraction service in site_config.json")
    
    def extract_with_gemini(self, file_doc):
        """Google Gemini API use karke extraction (FREE tier available)"""
        try:
            api_key = frappe.conf.get("gemini_api_key")
            if not api_key:
                frappe.throw("Gemini API key not configured. Add 'gemini_api_key' in site_config.json")
            
            # Verify API key format
            if not api_key.startswith("AIzaSy"):
                frappe.throw("Invalid Gemini API key format. Key should start with 'AIzaSy'")
            
            # File content read karna
            file_path = file_doc.get_full_path()
            
            # PDF ko base64 encode karna
            with open(file_path, 'rb') as f:
                pdf_content = base64.b64encode(f.read()).decode('utf-8')
            
            # Multiple API endpoints to try with CORRECT model names
            endpoints_to_try = [
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
            ]
            
            prompt = """
            This is a MULTIPAGE INVOICE PDF. It can be either:
            1. NORMAL INVOICE FORMAT - with item_code, qty, rate, amount
            2. BILL OF SUPPLY FORMAT - with item_code, box, packing, unit, quantity, rate, amount
            
            Extract the following information from ALL PAGES:
            
            IMPORTANT INSTRUCTIONS:
            - Read ALL pages of the PDF carefully
            - Detect invoice format automatically (Normal or Bill of Supply)
            - Customer name and invoice date are usually on the FIRST page
            - Items may be spread across MULTIPLE pages
            - Extract ALL items from ALL pages (do not skip any items)
            - Avoid duplicate items (if header repeats on each page)
            - Grand total and tax are usually on the LAST page
            
            FOR BILL OF SUPPLY FORMAT:
            Look for table with columns: SL.NO, ITEM NO, BOX, PACKING, UNIT, QUANTITY, RATE, AMOUNT
            
            Extract these EXACT values for each item:
            1. item_code: From ITEM NO column
            2. qty: From BOX column (number of boxes sold)
            3. conversion_factor: From PACKING column (items per box)
            4. stock_uom: From UNIT column (e.g., PCS, DOZ, KG)
            5. stock_qty: From QUANTITY column (should equal BOX × PACKING)
            6. stock_rate: From RATE column (rate per stock UOM, NOT box rate)
            7. amount: From AMOUNT column (total amount)
            
            CRITICAL FOR BILL OF SUPPLY:
            - "qty" = BOX value (sales quantity in boxes)
            - "conversion_factor" = PACKING value
            - "stock_uom" = UNIT value (PCS, DOZ, KG, etc.)
            - "stock_qty" = QUANTITY value
            - "stock_rate" = RATE value (this is rate per stock UOM, e.g., ₹20 per PCS)
            - "amount" = AMOUNT value
            - DO NOT calculate box_rate - we will do it later
            
            Example Bill of Supply row:
            | 1 | ITEM001 | 10 | 12 | PCS | 120 | 50 | 6000 |
            
            Should extract as:
            {
                "item_code": "ITEM001",
                "qty": 10,
                "conversion_factor": 12,
                "stock_uom": "PCS",
                "stock_qty": 120,
                "stock_rate": 50,
                "amount": 6000
            }
            
            FOR NORMAL INVOICE FORMAT:
            If standard invoice with just item, qty, rate, amount:
            - item_code: Item number/code
            - item_name: Item description
            - qty: Quantity
            - rate: Rate per unit
            - amount: Total amount
            
            Extract:
            1. invoice_type: "bill_of_supply" or "normal_invoice"
            2. customer_name: Customer name (exact as shown)
            3. invoice_date: Invoice date (format: YYYY-MM-DD)
            4. items: Array of items based on format detected
            5. total_amount: Grand total from last page
            6. discount_percent: Discount percentage if shown (extract the % value, e.g., 5 for 5%)
            7. discount_amount: Discount amount if shown in currency
            8. tax_amount: Total tax (0 for Bill of Supply usually)
            9. page_count: Number of pages processed
            
            Return ONLY a valid JSON object:
            
            FOR BILL OF SUPPLY:
            {
                "invoice_type": "bill_of_supply",
                "customer_name": "string",
                "invoice_date": "YYYY-MM-DD",
                "items": [
                    {
                        "item_code": "string",
                        "qty": number (BOX value),
                        "conversion_factor": number (PACKING value),
                        "stock_uom": "string (UNIT value like PCS/DOZ/KG)",
                        "stock_qty": number (QUANTITY value),
                        "stock_rate": number (RATE value - per stock UOM),
                        "amount": number (AMOUNT value)
                    }
                ],
                "total_amount": number,
                "discount_percent": number (optional, e.g., 5 for 5%),
                "discount_amount": number (optional),
                "tax_amount": number,
                "page_count": number
            }
            
            FOR NORMAL INVOICE:
            {
                "invoice_type": "normal_invoice",
                "customer_name": "string",
                "invoice_date": "YYYY-MM-DD",
                "items": [
                    {
                        "item_code": "string",
                        "item_name": "string",
                        "qty": number,
                        "rate": number,
                        "amount": number
                    }
                ],
                "total_amount": number,
                "discount_percent": number (optional),
                "discount_amount": number (optional),
                "tax_amount": number,
                "page_count": number
            }
            
            CRITICAL: 
            - For Bill of Supply, extract "stock_rate" (rate per stock UOM), NOT box rate
            - Do NOT calculate any derived values, extract exactly what's in PDF
            - Process EVERY page
            - Include ALL items from ALL pages
            - Return ONLY valid JSON, no markdown, no extra text
            """
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_content
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "topK": 1,
                    "topP": 1,
                    "maxOutputTokens": 4096
                }
            }
            
            # Try each endpoint
            last_error = None
            for idx, url in enumerate(endpoints_to_try):
                try:
                    frappe.logger().info(f"Trying Gemini endpoint {idx + 1}")
                    
                    response = requests.post(
                        url, 
                        json=payload, 
                        timeout=30,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        if result.get("candidates"):
                            text_response = result["candidates"][0]["content"]["parts"][0]["text"]
                            
                            # JSON extract karna (markdown code blocks ko handle karna)
                            text_response = text_response.strip()
                            if text_response.startswith("```json"):
                                text_response = text_response[7:]
                            if text_response.startswith("```"):
                                text_response = text_response[3:]
                            if text_response.endswith("```"):
                                text_response = text_response[:-3]
                            
                            extracted_data = json.loads(text_response.strip())
                            
                            # Multipage validation
                            if extracted_data.get("page_count"):
                                frappe.msgprint(
                                    f"Processed {extracted_data['page_count']} pages. "
                                    f"Found {len(extracted_data.get('items', []))} items.",
                                    indicator="blue"
                                )
                            
                            # Log multipage processing notes
                            if extracted_data.get("notes"):
                                frappe.logger().info(f"Multipage Notes: {extracted_data['notes']}")
                            
                            # Data validation
                            extracted_data = self.validate_extracted_data(extracted_data)
                            
                            return extracted_data
                        else:
                            last_error = "No candidates in response"
                            continue
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        continue
                        
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    continue
            
            # All endpoints failed
            if "404" in str(last_error):
                frappe.throw(f"""
                    Gemini API Error: Model not found (404)
                    
                    Solutions:
                    1. Generate new API key: https://makersuite.google.com/app/apikey
                    2. Enable Generative Language API in Google Cloud Console
                    3. Wait 2-3 minutes after enabling
                    
                    Current error: {last_error}
                """)
            elif "403" in str(last_error):
                frappe.throw("Gemini API Error: Permission denied. Enable the Generative Language API in Google Cloud Console.")
            else:
                frappe.throw(f"Gemini API extraction failed: {last_error}")
            
        except json.JSONDecodeError as e:
            frappe.log_error(f"JSON parsing error: {str(e)}", "PDF Extraction")
            frappe.throw("Failed to parse AI response. The response was not valid JSON.")
        except Exception as e:
            frappe.log_error(f"Gemini API Error: {str(e)}", "PDF Extraction")
            frappe.throw(f"PDF extraction failed: {str(e)}")
    
    def extract_with_openai(self, file_doc):
        """OpenAI GPT-4 Vision API use karke extraction"""
        try:
            api_key = frappe.conf.get("openai_api_key")
            if not api_key:
                frappe.throw("OpenAI API key not configured")
            
            # File content read karna
            file_path = file_doc.get_full_path()
            
            with open(file_path, 'rb') as f:
                pdf_content = base64.b64encode(f.read()).decode('utf-8')
            
            url = "https://api.openai.com/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            prompt = """Extract invoice data and return as JSON:
            {
                "customer_name": "string",
                "invoice_date": "YYYY-MM-DD",
                "items": [{"item_code": "string", "item_name": "string", "qty": number, "rate": number, "amount": number}],
                "total_amount": number,
                "tax_amount": number
            }"""
            
            payload = {
                "model": "gpt-4-vision-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:application/pdf;base64,{pdf_content}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1000
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            extracted_text = result["choices"][0]["message"]["content"]
            extracted_data = json.loads(extracted_text)
            
            return self.validate_extracted_data(extracted_data)
            
        except Exception as e:
            frappe.log_error(f"OpenAI API Error: {str(e)}", "PDF Extraction")
            frappe.throw(f"OpenAI extraction failed: {str(e)}")
    
    def extract_with_azure(self, file_doc):
        """Azure Document Intelligence use karke extraction"""
        try:
            endpoint = frappe.conf.get("azure_doc_intelligence_endpoint")
            api_key = frappe.conf.get("azure_doc_intelligence_key")
            
            if not endpoint or not api_key:
                frappe.throw("Azure credentials not configured")
            
            file_path = file_doc.get_full_path()
            
            # Azure Form Recognizer API call
            url = f"{endpoint}/formrecognizer/documentModels/prebuilt-invoice:analyze?api-version=2023-07-31"
            
            headers = {
                "Ocp-Apim-Subscription-Key": api_key,
                "Content-Type": "application/pdf"
            }
            
            with open(file_path, 'rb') as f:
                response = requests.post(url, headers=headers, data=f, timeout=30)
            
            response.raise_for_status()
            
            # Get operation location
            operation_url = response.headers["Operation-Location"]
            
            # Poll for results
            import time
            for _ in range(10):
                time.sleep(2)
                result_response = requests.get(
                    operation_url,
                    headers={"Ocp-Apim-Subscription-Key": api_key}
                )
                result = result_response.json()
                
                if result["status"] == "succeeded":
                    return self.parse_azure_response(result)
            
            frappe.throw("Azure processing timeout")
            
        except Exception as e:
            frappe.log_error(f"Azure API Error: {str(e)}", "PDF Extraction")
            frappe.throw(f"Azure extraction failed: {str(e)}")
    
    def parse_azure_response(self, azure_result):
        """Azure response ko parse karke data extract karna"""
        documents = azure_result.get("analyzeResult", {}).get("documents", [])
        
        if not documents:
            return {}
        
        doc = documents[0]
        fields = doc.get("fields", {})
        
        extracted_data = {
            "customer_name": fields.get("CustomerName", {}).get("content", ""),
            "invoice_date": fields.get("InvoiceDate", {}).get("content", frappe.utils.today()),
            "items": [],
            "total_amount": fields.get("InvoiceTotal", {}).get("content", 0),
            "tax_amount": fields.get("TotalTax", {}).get("content", 0)
        }
        
        # Items extract karna
        items = fields.get("Items", {}).get("valueArray", [])
        for item in items:
            item_fields = item.get("valueObject", {})
            extracted_data["items"].append({
                "item_code": item_fields.get("ProductCode", {}).get("content", ""),
                "item_name": item_fields.get("Description", {}).get("content", ""),
                "qty": float(item_fields.get("Quantity", {}).get("content", 1)),
                "rate": float(item_fields.get("UnitPrice", {}).get("content", 0)),
                "amount": float(item_fields.get("Amount", {}).get("content", 0))
            })
        
        return extracted_data
    
    def validate_extracted_data(self, data):
        """Extracted data ko validate aur clean karna"""
        
        # Remove duplicate items (common in multipage invoices)
        if data.get("items"):
            unique_items = []
            seen_items = set()
            
            for item in data["items"]:
                # Create unique key from item_code and amount
                item_key = f"{item.get('item_code', '')}_{item.get('amount', 0)}"
                
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    unique_items.append(item)
                else:
                    frappe.logger().info(f"Removed duplicate item: {item.get('item_code')}")
            
            data["items"] = unique_items
            
            # Log if duplicates were found
            original_count = len(data.get("items", []))
            if original_count != len(unique_items):
                frappe.msgprint(
                    f"Removed {original_count - len(unique_items)} duplicate items",
                    indicator="orange"
                )
        
        # Customer name validation
        if data.get("customer_name"):
            customer_name = data["customer_name"].strip()
            
            # ERPNext mein customer exist karta hai check karna
            if not frappe.db.exists("Customer", customer_name):
                # Similar customer dhundna
                similar = frappe.db.get_all(
                    "Customer",
                    filters={"customer_name": ["like", f"%{customer_name[:10]}%"]},
                    limit=1
                )
                if similar:
                    data["customer_name"] = similar[0].name
                else:
                    # New customer suggest karna
                    data["_customer_not_found"] = True
        
        # Date validation
        if data.get("invoice_date"):
            try:
                from frappe.utils import getdate
                data["invoice_date"] = str(getdate(data["invoice_date"]))
            except:
                data["invoice_date"] = frappe.utils.today()
        
        # Items validation
        validated_items = []
        for item in data.get("items", []):
            if item.get("item_code"):
                # Item exist karta hai check karna
                if frappe.db.exists("Item", item["item_code"]):
                    validated_items.append(item)
                else:
                    # Item ka fallback
                    item["_item_not_found"] = True
                    validated_items.append(item)
        
        data["items"] = validated_items
        
        # Validate totals match sum of items
        items_total = sum(item.get("amount", 0) for item in data.get("items", []))
        declared_total = data.get("total_amount", 0)
        
        # Allow 1% variance for rounding differences
        if items_total > 0 and abs(items_total - declared_total) / items_total > 0.01:
            frappe.msgprint(
                f"Warning: Items total (₹{items_total:.2f}) doesn't match declared total (₹{declared_total:.2f})",
                indicator="orange"
            )
            data["_total_mismatch"] = True
        
        return data
    
    def create_sales_invoice(self, extracted_data):
        """Create invoice with correct Box rate calculation for Bill of Supply"""
        
        customer = extracted_data.get("customer_name")
        if not customer or extracted_data.get("_customer_not_found"):
            frappe.throw(f"Customer '{customer}' not found in ERPNext. Please create customer first.")
        
        invoice_type = extracted_data.get("invoice_type", "normal_invoice")
        
        # Create invoice
        invoice = frappe.new_doc("Sales Invoice")
        invoice.customer = customer
        invoice.posting_date = extracted_data.get("invoice_date", frappe.utils.today())
        invoice.due_date = frappe.utils.add_days(invoice.posting_date, 30)
        
        # Apply discount if present
        discount_percent = extracted_data.get("discount_percent", 0)
        discount_amount = extracted_data.get("discount_amount", 0)
        
        if discount_percent > 0:
            invoice.additional_discount_percentage = float(discount_percent)
            frappe.logger().info(f"Applied discount: {discount_percent}%")
        elif discount_amount > 0:
            invoice.discount_amount = float(discount_amount)
            frappe.logger().info(f"Applied discount amount: ₹{discount_amount}")
        
        # Add items
        if invoice_type == "bill_of_supply":
            for item_data in extracted_data.get("items", []):
                if item_data.get("_item_not_found"):
                    frappe.msgprint(f"Item '{item_data.get('item_code')}' not found. Skipping.", indicator="orange")
                    continue
                
                # CRITICAL CALCULATION:
                # PDF RATE = stock UOM rate (per PCS)
                # ERPNext needs Box rate = PACKING × PDF_RATE
                
                qty = float(item_data.get("qty", 1))  # BOX
                conversion_factor = float(item_data.get("conversion_factor", 1))  # PACKING
                stock_rate = float(item_data.get("stock_rate", 0))  # PDF RATE (per stock UOM)
                stock_uom = item_data.get("stock_uom", "Nos")  # UNIT
                
                # Calculate Box rate
                box_rate = conversion_factor * stock_rate
                
                # Add row with calculated Box rate
                row = invoice.append("items", {
                    "item_code": item_data["item_code"],
                    "qty": qty,
                    "uom": "Box",  # ALWAYS Box for Bill of Supply
                    "rate": box_rate  # This is rate per Box
                })
                
                # Set stock fields IMMEDIATELY after append
                row.stock_uom = stock_uom
                row.conversion_factor = conversion_factor
                row.stock_qty = float(item_data.get("stock_qty", qty * conversion_factor))
                
                # Log for debugging
                frappe.logger().info(
                    f"{item_data['item_code']}: "
                    f"Qty={qty} Box, CF={conversion_factor}, "
                    f"Stock Rate={stock_rate}/{stock_uom}, Box Rate={box_rate}, "
                    f"Stock Qty={row.stock_qty} {stock_uom}"
                )
                
        else:
            # Normal invoice
            for item_data in extracted_data.get("items", []):
                if item_data.get("_item_not_found"):
                    continue
                    
                invoice.append("items", {
                    "item_code": item_data["item_code"],
                    "item_name": item_data.get("item_name", ""),
                    "qty": float(item_data.get("qty", 1)),
                    "rate": float(item_data.get("rate", 0))
                })
        
        if not invoice.items:
            frappe.throw("No valid items found to create invoice")
        
        # Insert invoice
        invoice.insert(ignore_permissions=True)
        
        # Apply discount for ALL invoice types (not just Bill of Supply)
        discount_applied = False
        
        if discount_percent > 0:
            frappe.db.sql("""
                UPDATE `tabSales Invoice`
                SET 
                    additional_discount_percentage = %s,
                    apply_discount_on = 'Grand Total'
                WHERE name = %s
            """, (float(discount_percent), invoice.name))
            discount_applied = True
            frappe.logger().info(f"Applied discount: {discount_percent}%")
            
        elif discount_amount > 0:
            frappe.db.sql("""
                UPDATE `tabSales Invoice`
                SET discount_amount = %s
                WHERE name = %s
            """, (float(discount_amount), invoice.name))
            discount_applied = True
            frappe.logger().info(f"Applied discount amount: ₹{discount_amount}")
        
        if discount_applied:
            frappe.db.commit()
        
        # FORCE CORRECTION for Bill of Supply: Ensure UOM is "Box" and stock fields are correct
        if invoice_type == "bill_of_supply":
            extracted_items = {item["item_code"]: item 
                              for item in extracted_data.get("items", [])}
            
            needs_correction = False
            
            for row in invoice.items:
                if row.item_code in extracted_items:
                    expected = extracted_items[row.item_code]
                    
                    expected_stock_uom = expected.get("stock_uom", "Nos")
                    expected_cf = float(expected.get("conversion_factor", 1))
                    expected_stock_qty = float(expected.get("stock_qty", 0))
                    
                    # Check if correction needed
                    if (row.uom != "Box" or
                        row.stock_uom != expected_stock_uom or 
                        abs(row.conversion_factor - expected_cf) > 0.01 or
                        abs(row.stock_qty - expected_stock_qty) > 0.01):
                        
                        needs_correction = True
                        
                        frappe.logger().info(
                            f"Correcting {row.item_code}: "
                            f"UOM {row.uom}→Box, "
                            f"Stock UOM {row.stock_uom}→{expected_stock_uom}, "
                            f"CF {row.conversion_factor}→{expected_cf}"
                        )
                        
                        # Force with SQL
                        frappe.db.sql("""
                            UPDATE `tabSales Invoice Item`
                            SET 
                                uom = 'Box',
                                stock_uom = %s,
                                conversion_factor = %s,
                                stock_qty = %s
                            WHERE name = %s
                        """, (
                            expected_stock_uom,
                            expected_cf,
                            expected_stock_qty,
                            row.name
                        ))
            
            if needs_correction:
                frappe.db.commit()
                invoice.reload()
            
            # CRITICAL: Force discount using SQL if needed
            needs_discount_update = False
            
            if discount_percent > 0:
                current_discount = invoice.additional_discount_percentage or 0
                if abs(current_discount - discount_percent) > 0.01:
                    needs_discount_update = True
                    frappe.db.sql("""
                        UPDATE `tabSales Invoice`
                        SET 
                            additional_discount_percentage = %s,
                            apply_discount_on = 'Grand Total'
                        WHERE name = %s
                    """, (float(discount_percent), invoice.name))
                    frappe.logger().info(f"Force updated discount: {discount_percent}%")
                    
            elif discount_amount > 0:
                current_discount_amt = invoice.discount_amount or 0
                if abs(current_discount_amt - discount_amount) > 0.01:
                    needs_discount_update = True
                    frappe.db.sql("""
                        UPDATE `tabSales Invoice`
                        SET discount_amount = %s
                        WHERE name = %s
                    """, (float(discount_amount), invoice.name))
                    frappe.logger().info(f"Force updated discount amount: ₹{discount_amount}")
            
            if needs_discount_update:
                frappe.db.commit()
                invoice.reload()
            
            # Verify totals
            total_calculated = sum(row.amount for row in invoice.items)
            pdf_total = extracted_data.get("total_amount", 0)
            discount_info = ""
            
            if discount_percent > 0:
                discount_info = f" (Discount: {discount_percent}%)"
            elif discount_amount > 0:
                discount_info = f" (Discount: ₹{discount_amount})"
            
            if abs(total_calculated - pdf_total) > 1:
                frappe.msgprint(
                    f"⚠️ Total mismatch: Invoice=₹{total_calculated:.2f}, "
                    f"PDF=₹{pdf_total:.2f}{discount_info}",
                    indicator="orange"
                )
            else:
                frappe.msgprint(
                    f"✅ Bill of Supply created. Total: ₹{total_calculated:.2f}{discount_info}",
                    indicator="green"
                )
        
        # Auto-submit
        if self.auto_submit:
            invoice.submit()
        
        return invoice
    
    @frappe.whitelist()
    def preview_extracted_data(self):
        """Extracted data ka preview without creating invoice"""
        if self.pdf_file:
            file_doc = frappe.get_doc("File", {"file_url": self.pdf_file})
            extracted_data = self.extract_pdf_using_api(file_doc)
            return extracted_data
        return {}
    
    @frappe.whitelist()
    def verify_gemini_api_key(self):
        """Verify if Gemini API key is working"""
        api_key = frappe.conf.get("gemini_api_key")
        
        if not api_key:
            return {
                "success": False,
                "message": "API key not configured in site_config.json"
            }
        
        # Test endpoints with CORRECT model names
        test_endpoints = [
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        ]
        
        payload = {
            "contents": [{
                "parts": [{"text": "Say 'API is working' if you can read this."}]
            }]
        }
        
        for url in test_endpoints:
            try:
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("candidates"):
                        return {
                            "success": True,
                            "message": "✅ Gemini API is working correctly!",
                            "endpoint": url.split('?')[0],
                            "model": "gemini-2.0-flash"
                        }
            except Exception as e:
                continue
        
        return {
            "success": False,
            "message": "❌ API key verification failed",
            "suggestion": "Generate new key at: https://makersuite.google.com/app/apikey"
        }