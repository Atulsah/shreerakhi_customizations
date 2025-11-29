# Copyright (c) 2024, Atul Sah
# Simplified Version - Auto-numbering with Series Selection Only

import frappe
from frappe.model.document import Document
import json
import requests
import base64
from frappe.utils import get_files_path
import os

class InvoicePDFUpload(Document):
    def validate(self):
        # Validate PDF is present for new documents or if not yet processed
        if self.is_new() and not self.pdf_file:
            frappe.throw("Please upload a PDF file")
        
        # Validate invoice series if auto-create is enabled
        if self.auto_create_invoice:
            if not self.invoice_series:
                frappe.throw("Please select an Invoice Series")
        
        # Only process if PDF exists and invoice not yet created
        if self.pdf_file and not self.sales_invoice and self.auto_create_invoice:
            self.extract_and_create_invoice()
    
    def extract_and_create_invoice(self):
        """PDF se data extract karke Sales Invoice create karta hai"""
        file_name = None
        file_path = None
        
        try:
            # PDF file read karna
            file_doc = frappe.get_doc("File", {"file_url": self.pdf_file})
            
            # Store file info for later deletion (but don't delete yet!)
            file_path = file_doc.get_full_path()
            file_name = file_doc.name
            
            # API se data extract karna
            extracted_data = self.extract_pdf_using_api(file_doc)
            
            # Extracted data ko JSON field mein store karna
            self.extracted_data = json.dumps(extracted_data, indent=2)
            
            # Set detected invoice type
            if extracted_data.get("invoice_type") == "bill_of_supply":
                self.detected_invoice_type = "Bill of Supply"
            else:
                self.detected_invoice_type = "Normal Invoice"
            
            # Sales Invoice create karna with auto-numbering
            if extracted_data and extracted_data.get("customer_name"):
                invoice = self.create_sales_invoice(extracted_data)
                self.sales_invoice = invoice.name
                self.invoice_status = "Processed"
                
                frappe.msgprint(f"Sales Invoice {invoice.name} successfully created with auto-numbering!")
            else:
                self.invoice_status = "Failed"
                frappe.msgprint("Could not extract sufficient data from PDF", indicator="red")
            
        except Exception as e:
            self.invoice_status = "Failed"
            self.error_log = str(e)
            frappe.log_error(f"Error in PDF extraction: {str(e)}", "Invoice PDF Upload Error")
            frappe.throw(f"PDF extraction failed: {str(e)}")
    
    def on_update(self):
        """Called after document is saved - safe to delete PDF here"""
        # Only delete if processing was successful and option is enabled
        if (self.invoice_status == "Processed" and 
            self.delete_pdf_after_processing and 
            self.pdf_file):
            
            try:
                # Get file info
                file_doc = frappe.get_doc("File", {"file_url": self.pdf_file})
                file_path = file_doc.get_full_path()
                file_name = file_doc.name
                
                # Delete PDF file
                self.delete_pdf_file(file_name, file_path)
                
                frappe.msgprint("PDF deleted to save storage space.", indicator="blue")
                
            except Exception as e:
                frappe.log_error(f"Error deleting PDF in on_update: {str(e)}", "PDF Deletion Error")
    
    def delete_pdf_file(self, file_name, file_path):
        """Delete PDF file after successful extraction to save space"""
        try:
            # Delete file from database
            if frappe.db.exists("File", file_name):
                frappe.delete_doc("File", file_name, ignore_permissions=True, force=True)
                frappe.logger().info(f"Deleted File record: {file_name}")
            
            # Delete physical file from server
            if os.path.exists(file_path):
                os.remove(file_path)
                frappe.logger().info(f"Deleted physical file: {file_path}")
            
            # Update current document to clear pdf_file reference
            frappe.db.set_value("Invoice PDF Upload", self.name, "pdf_file", None, update_modified=False)
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(f"Error deleting PDF file: {str(e)}", "PDF Deletion Error")
    
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
            
            if not api_key.startswith("AIzaSy"):
                frappe.throw("Invalid Gemini API key format. Key should start with 'AIzaSy'")
            
            file_path = file_doc.get_full_path()
            
            with open(file_path, 'rb') as f:
                pdf_content = base64.b64encode(f.read()).decode('utf-8')
            
            endpoints_to_try = [
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
            ]
            
            prompt = """
            This is a MULTIPAGE INVOICE PDF. Extract the following information from ALL PAGES:
            
            IMPORTANT: DO NOT extract invoice number - system will auto-generate it.
            
            Detect invoice format:
            1. NORMAL INVOICE - with item_code, qty, rate, amount
            2. BILL OF SUPPLY - with item_code, box, packing, unit, quantity, rate, amount
            
            FOR BILL OF SUPPLY FORMAT:
            Extract from table with columns: SL.NO, ITEM NO, BOX, PACKING, UNIT, QUANTITY, RATE, AMOUNT
            
            Extract:
            1. item_code: From ITEM NO column
            2. qty: From BOX column (boxes sold)
            3. conversion_factor: From PACKING column (items per box)
            4. stock_uom: From UNIT column (PCS, DOZ, KG, etc.)
            5. stock_qty: From QUANTITY column
            6. stock_rate: From RATE column (rate per stock UOM)
            7. amount: From AMOUNT column
            
            FOR NORMAL INVOICE:
            - item_code: Item code
            - item_name: Item description
            - qty: Quantity
            - rate: Rate per unit
            - amount: Total amount
            
            Extract:
            1. invoice_type: "bill_of_supply" or "normal_invoice"
            2. customer_name: Customer name
            3. invoice_date: Date (YYYY-MM-DD)
            4. items: Array of items
            5. total_amount: Grand total
            6. discount_percent: Discount % (if exists)
            7. discount_amount: Discount amount (if exists)
            8. tax_amount: Tax amount
            9. page_count: Pages processed
            
            Return ONLY valid JSON - no invoice_number field needed (auto-generated).
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
                            
                            text_response = text_response.strip()
                            if text_response.startswith("```json"):
                                text_response = text_response[7:]
                            if text_response.startswith("```"):
                                text_response = text_response[3:]
                            if text_response.endswith("```"):
                                text_response = text_response[:-3]
                            
                            extracted_data = json.loads(text_response.strip())
                            
                            if extracted_data.get("page_count"):
                                frappe.msgprint(
                                    f"Processed {extracted_data['page_count']} pages. "
                                    f"Found {len(extracted_data.get('items', []))} items.",
                                    indicator="blue"
                                )
                            
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
            
            if "404" in str(last_error):
                frappe.throw(f"Gemini API Error: Model not found. Generate new key at https://makersuite.google.com/app/apikey")
            elif "403" in str(last_error):
                frappe.throw("Gemini API Error: Permission denied. Enable the Generative Language API.")
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
            
            file_path = file_doc.get_full_path()
            
            with open(file_path, 'rb') as f:
                pdf_content = base64.b64encode(f.read()).decode('utf-8')
            
            url = "https://api.openai.com/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            prompt = """Extract invoice data and return as JSON (NO invoice_number field):
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
            
            url = f"{endpoint}/formrecognizer/documentModels/prebuilt-invoice:analyze?api-version=2023-07-31"
            
            headers = {
                "Ocp-Apim-Subscription-Key": api_key,
                "Content-Type": "application/pdf"
            }
            
            with open(file_path, 'rb') as f:
                response = requests.post(url, headers=headers, data=f, timeout=30)
            
            response.raise_for_status()
            
            operation_url = response.headers["Operation-Location"]
            
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
        
        # Remove duplicate items
        if data.get("items"):
            unique_items = []
            seen_items = set()
            
            for item in data["items"]:
                item_key = f"{item.get('item_code', '')}_{item.get('amount', 0)}"
                
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    unique_items.append(item)
            
            data["items"] = unique_items
        
        # Customer validation
        if data.get("customer_name"):
            customer_name = data["customer_name"].strip()
            
            if not frappe.db.exists("Customer", customer_name):
                similar = frappe.db.get_all(
                    "Customer",
                    filters={"customer_name": ["like", f"%{customer_name[:10]}%"]},
                    limit=1
                )
                if similar:
                    data["customer_name"] = similar[0].name
                else:
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
                if frappe.db.exists("Item", item["item_code"]):
                    validated_items.append(item)
                else:
                    item["_item_not_found"] = True
                    validated_items.append(item)
        
        data["items"] = validated_items
        
        return data
    
    def create_sales_invoice(self, extracted_data):
        """Create invoice with auto-numbering based on selected series"""
        
        customer = extracted_data.get("customer_name")
        if not customer or extracted_data.get("_customer_not_found"):
            frappe.throw(f"Customer '{customer}' not found in ERPNext. Please create customer first.")
        
        invoice_type = extracted_data.get("invoice_type", "normal_invoice")
        
        # Create invoice with auto-numbering
        invoice = frappe.new_doc("Sales Invoice")
        invoice.customer = customer
        invoice.posting_date = extracted_data.get("invoice_date", frappe.utils.today())
        invoice.due_date = frappe.utils.add_days(invoice.posting_date, 30)
        
        # Set naming series - ERPNext will auto-generate number
        invoice.naming_series = self.invoice_series
        
        discount_percent = extracted_data.get("discount_percent")
        discount_amount = extracted_data.get("discount_amount")
        
        # Apply discount if present
        if discount_percent and float(discount_percent) > 0:
            invoice.additional_discount_percentage = float(discount_percent)
        elif discount_amount and float(discount_amount) > 0:
            invoice.discount_amount = float(discount_amount)
        
        # Add items
        if invoice_type == "bill_of_supply":
            for item_data in extracted_data.get("items", []):
                if item_data.get("_item_not_found"):
                    continue
                
                qty = float(item_data.get("qty", 1))
                conversion_factor = float(item_data.get("conversion_factor", 1))
                stock_rate = float(item_data.get("stock_rate", 0))
                stock_uom = item_data.get("stock_uom", "Nos")
                
                box_rate = conversion_factor * stock_rate
                
                row = invoice.append("items", {
                    "item_code": item_data["item_code"],
                    "qty": qty,
                    "uom": "Box",
                    "rate": box_rate
                })
                
                row.stock_uom = stock_uom
                row.conversion_factor = conversion_factor
                row.stock_qty = float(item_data.get("stock_qty", qty * conversion_factor))
        else:
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
        
        # Insert invoice - ERPNext will auto-generate the invoice number
        invoice.insert(ignore_permissions=True)
        
        # Log the auto-generated invoice number
        frappe.logger().info(f"Created invoice with auto-number: {invoice.name}")
        
        # Auto-submit if enabled
        if self.auto_submit:
            invoice.submit()
        
        return invoice
    
    @frappe.whitelist()
    def preview_extracted_data(self):
        """Extracted data ka preview"""
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


@frappe.whitelist()
def debug_invoice_discount(invoice_name):
    """Debug discount values"""
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    
    return {
        "invoice_name": invoice_name,
        "additional_discount_percentage": invoice.additional_discount_percentage,
        "discount_amount": invoice.discount_amount,
        "total": invoice.total,
        "grand_total": invoice.grand_total
    }