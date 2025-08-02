from django.shortcuts import render
from django.core.files.storage import default_storage
import fitz  # PyMuPDF
import pandas as pd
import re
import os
import tempfile
from datetime import datetime
from django.http import FileResponse

def split_pdf_chunks(file_path, pages_per_chunk=10):
    print("Splitting PDF into chunks")
    doc = fitz.open(file_path)
    chunks = []
    for start in range(0, len(doc), pages_per_chunk):
        end = min(start + pages_per_chunk, len(doc))
        print(f"Creating chunk from page {start} to {end - 1}")
        sub_doc = fitz.open()
        for p in range(start, end):
            sub_doc.insert_pdf(doc, from_page=p, to_page=p)
        chunks.append(sub_doc)
    print(f"✅ Total chunks created: {len(chunks)}")
    return chunks


def meeshoindex(request):
    message = None
    if request.method == "POST" and request.FILES.get("pdf_file"):
        uploaded_file = request.FILES["pdf_file"]
        temp_file_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)

        with open(temp_file_path, 'wb+') as temp_file: 
            for chunk in uploaded_file.chunks(): 
                temp_file.write(chunk) 

        try:
            # Read full PDF text
            doc = fitz.open(temp_file_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()

            # Split by Customer Address blocks
            label_blocks = full_text.split("Customer Address")
            extracted_data = []

            for block in label_blocks[1:]:
                block_text = "Customer Address" + block

                # ----------------- Customer Address -----------------
                customer_address = extract_customer_address(block_text)
                
                # ----------------- Order Date -----------------
                order_date = extract_order_date(block_text)

                # ----------------- Invoice Date -----------------
                invoice_date = extract_invoice_date(block_text)

                # ----------------- GSTIN -----------------
                gstin = extract_gstin(block_text)

                # ----------------- AWB Number -----------------
                awb_number = extract_awb_number(block_text)

                # ----------------- Pickup Courier Partner -----------------
                pickup = extract_pickup_partner(block_text)

                # ----------------- Product Info -----------------
                product_info = extract_product_info(block_text)

                # ----------------- Add to Extracted List -----------------
                extracted_data.append({
                    "SKU": product_info.get("sku", ""),
                    "Size": product_info.get("size", ""),
                    "Qty": product_info.get("qty", ""),
                    "Color": product_info.get("color", ""),
                    "Order No.": product_info.get("order_no", ""),
                    "Order Date": order_date,
                    "Invoice Date": invoice_date,
                    "GSTIN": gstin,
                    "AWB Number": awb_number,
                    "Pickup": pickup,
                    "Customer Address": customer_address
                })

            # ----------------- Save to Excel -----------------
            if extracted_data:
                df = pd.DataFrame(extracted_data)[[
                    "SKU",
                    "Size",
                    "Qty",
                    "Color",
                    "Order No.",
                    "Order Date",
                    "Invoice Date",
                    "GSTIN",
                    "AWB Number",
                    "Pickup",
                    "Customer Address"
                ]]

                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", dir=tempfile.gettempdir()) as tmp_file:  # ✅ NEW
                    df.to_excel(tmp_file.name, index=False)
                    tmp_file.flush()
                    tmp_file_path = tmp_file.name

                message = f"✅ {len(extracted_data)} labels extracted and saved."
                response = FileResponse(open(tmp_file_path, 'rb'), as_attachment=True, filename=os.path.basename(tmp_file_path))
                return response
            else:
                message = "❌ No data extracted from PDF"

        except Exception as e:
            message = f"❌ Error processing PDF: {str(e)}"
        finally:
            # Clean up uploaded file
            if os.path.exists(temp_file_path):  
                os.remove(temp_file_path)
    return render(request, "upload_file.html", {"message": message})


def extract_customer_address(block_text):
    """Extract customer address from block text"""
    try:
        match = re.search(
            r"Customer Address\s*\n(.+?)(?:If undelivered, return to:|Prepaid|Invoice|TAX INVOICE|Order No\.|SKU|GSTIN)",
            block_text,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            address_block = match.group(1)
            address_lines = address_block.strip().split("\n")
            address_lines = [line.strip() for line in address_lines if line.strip()]
            customer_address = ", ".join(address_lines)
    except Exception as e:
        print("❌ Error extracting customer address:", e)
        print(block_text[:500])
    return customer_address


def extract_order_date(block_text):
    """Extract order date from block text"""
    order_date = ""
    patterns = [
        r"Order\s*Date\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"Order\s*Dt\.?\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"Order\s*Placed\s*On\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"Ordered\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, block_text, re.IGNORECASE)
        if match:
            order_date = match.group(1)
            break
    return order_date

# 🔧 ADDED: If Order Date not found, try to extract "Dispatch on" date
    if not order_date:
        dispatch_match = re.search(r"Dispatch\s+on\s+[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", block_text, re.IGNORECASE)
        if dispatch_match:
            order_date = dispatch_match.group(1)

    return order_date


def extract_invoice_date(block_text):
    """Extract invoice date from block text"""
    invoice_date = ""
    patterns = [
        r"Invoice\s*Date\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"Invoice\s*Dt\.?\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"Invoice\s*Generated\s*On\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"Inv\.\s*Date\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, block_text, re.IGNORECASE)
        if match:
            invoice_date = match.group(1)
            break
    return invoice_date


def extract_gstin(block_text):
    """Extract GSTIN from block text"""
    gstin = ""
    gstin_match = re.search(r"GSTIN\s*[:\-]?\s*([0-9A-Z]{15})", block_text, re.IGNORECASE)
    if gstin_match:
        gstin = gstin_match.group(1)
    return gstin


def extract_awb_number(block_text):
    """Extract AWB number from block text"""
    awb_number = ""
    
    # Debug: Print block text to see what's available
    print("🔍 Searching for AWB in block:")
    print(block_text[:5000])  # Print first 500 chars
    
    # AWB patterns based on your examples:
    # VL0081530070753 (VL + 13 digits)
    # SF1556751037FPL (SF + 10 digits + FPL)  
    # 1490810673698592 (16 digits)
    # M00831998289 (M + 11 digits)
    
    patterns = [
        # Specific courier patterns
        r"AWB\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Z]{2}\d{10,15})",  # VL0081530070753
        r"AWB\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Z]{2}\d{10,13}[A-Z]{2,3})",  # SF1556751037FPL
        r"AWB\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Z]\d{10,15})",  # M00831998289
        r"AWB\s*(?:No\.?|Number)?\s*[:\-]?\s*(\d{13,16})",  # 1490810673698592
        
        # Tracking patterns
        r"Tracking\s*(?:No\.?|ID)?\s*[:\-]?\s*([A-Z]{2}\d{10,15})",
        r"Tracking\s*(?:No\.?|ID)?\s*[:\-]?\s*([A-Z]{2}\d{10,13}[A-Z]{2,3})",
        r"Tracking\s*(?:No\.?|ID)?\s*[:\-]?\s*([A-Z]\d{10,15})",
        r"Tracking\s*(?:No\.?|ID)?\s*[:\-]?\s*(\d{13,16})",
        
        # General patterns for various AWB formats
        r"(?:AWB|Tracking|Waybill|Docket|LR)\s*(?:No\.?|Number|ID)?\s*[:\-]?\s*([A-Z]{2}\d{10,15})",
        r"(?:AWB|Tracking|Waybill|Docket|LR)\s*(?:No\.?|Number|ID)?\s*[:\-]?\s*([A-Z]{2}\d{10,13}[A-Z]{2,3})",
        r"(?:AWB|Tracking|Waybill|Docket|LR)\s*(?:No\.?|Number|ID)?\s*[:\-]?\s*([A-Z]\d{10,15})",
        r"(?:AWB|Tracking|Waybill|Docket|LR)\s*(?:No\.?|Number|ID)?\s*[:\-]?\s*(\d{13,16})",
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, block_text, re.IGNORECASE)
        if match:
            potential_awb = match.group(1)
            # Validate AWB format
            if is_valid_awb(potential_awb):
                awb_number = potential_awb
                print(f"✅ AWB found with pattern {i+1}: {awb_number}")
                break
    
    # If no AWB found with labels, search for AWB patterns without labels
    if not awb_number:
        standalone_patterns = [
            r"\b([A-Z]{2}\d{10,15})\b",  # VL0081530070753
            r"\b([A-Z]{2}\d{10,13}[A-Z]{2,3})\b",  # SF1556751037FPL
            r"\b([A-Z]\d{10,15})\b",  # M00831998289
            r"\b(\d{13,16})\b"  # 1490810673698592
        ]
        
        for pattern in standalone_patterns:
            matches = re.findall(pattern, block_text, re.IGNORECASE)
            for match in matches:
                if is_valid_awb(match):
                    awb_number = match
                    print(f"✅ AWB found standalone: {awb_number}")
                    break
            if awb_number:
                break
    
    print(f"📦 Final AWB Number: {awb_number}")
    return awb_number


def is_valid_awb(awb_code):
    """Validate if the extracted code looks like a valid AWB number"""
    if not awb_code:
        return False
    
    # Remove spaces and convert to uppercase
    awb_code = awb_code.replace(" ", "").upper()
    
    # Check length (AWB numbers are usually 10-16 characters)
    if len(awb_code) < 10 or len(awb_code) > 16:
        return False
    
    # Valid AWB patterns based on your examples
    valid_patterns = [
        r"^[A-Z]{2}\d{10,15}$",  # VL0081530070753
        r"^[A-Z]{2}\d{10,13}[A-Z]{2,3}$",  # SF1556751037FPL
        r"^[A-Z]\d{10,15}$",  # M00831998289
        r"^\d{13,16}$"  # 1490810673698592
    ]
    
    for pattern in valid_patterns:
        if re.match(pattern, awb_code):
            return True
    
    return False


def extract_pickup_partner(block_text):
    """Extract pickup courier partner from block text"""
    pickup = ""
    known_couriers = [
        "Delhivery", "XpressBees", "Xpress Bees", "Ecom Express", "Shadowfax",
        "BlueDart", "Blue Dart", "Ekart", "Valmo", "DTDC", "Amazon Transportation", 
        "Wow Express", "FedEx", "DHL", "Shiprocket", "Pickrr", "Aramex", "Gati",
        "Professional Couriers", "DTDC Express", "India Post", "Speed Post"
    ]
    
    for courier in known_couriers:
        if re.search(rf"\b{re.escape(courier)}\b", block_text, re.IGNORECASE):
            pickup = courier
            break
    return pickup


def extract_product_info(block_text):
    """Extract product information from block text"""
    product_info = {
        "sku": "",
        "size": "",
        "qty": "",
        "color": "",
        "order_no": ""
    }
    
    try:
        # Find lines containing product data
        lines = block_text.splitlines()
        product_data_lines = []
        found_sku = False
        header_keywords = {"SKU", "Size", "Qty", "Color", "Order No.", "Order No"}

        for line in lines:
            clean_line = line.strip()
            if not found_sku and "SKU" in clean_line:
                found_sku = True
                continue
            if found_sku:
                if clean_line == "" or "Customer Address" in clean_line or "GSTIN" in clean_line:
                    break
                if clean_line in header_keywords:
                    continue
                product_data_lines.append(clean_line)

        # Join all product lines and split into words
        flat_data = []
        for line in product_data_lines:
            flat_data.extend(line.split())

        # Parse product data
        if len(flat_data) >= 5:
            # Check for "Free Size" pattern
            if "Free Size" in " ".join(flat_data):
                try:
                    free_idx = flat_data.index("Free")
                    size_idx = flat_data.index("Size", free_idx)
                    
                    if size_idx == free_idx + 1:  # "Free Size" is consecutive
                        product_info["sku"] = " ".join(flat_data[:free_idx])
                        product_info["size"] = "Free Size"
                        
                        # Get remaining fields after "Free Size"
                        remaining = flat_data[size_idx + 1:]
                        if len(remaining) >= 3:
                            product_info["qty"] = remaining[0]
                            product_info["color"] = remaining[1]
                            product_info["order_no"] = remaining[2]
                except ValueError:
                    pass
            
            # If Free Size parsing failed, try alternative parsing
            if not product_info["sku"]:
                # Look for numeric patterns that might indicate quantity
                qty_pattern = r'^\d+$'
                order_pattern = r'^\d{10,}$'  # Order numbers are typically long
                
                # Try to identify quantity and order number positions
                for i, item in enumerate(flat_data):
                    if re.match(qty_pattern, item) and len(item) <= 3:  # Qty is usually 1-3 digits
                        if i >= 2 and i + 2 < len(flat_data):
                            product_info["sku"] = " ".join(flat_data[:i-2])  # qty થી 2 પહેલા સુધી
                            product_info["size"] = flat_data[i-1]
                            product_info["qty"] = item
                            product_info["color"] = flat_data[i+1]
                            product_info["order_no"] = flat_data[i+2]
                            break
                
                # Fallback: assume last 4 items are size, qty, color, order_no
                if not product_info["sku"] and len(flat_data) >= 6:
                    product_info["size"] = flat_data[-5]
                    product_info["qty"] = flat_data[-4]
                    product_info["color"] = flat_data[-3]
                    product_info["order_no"] = flat_data[-2] + flat_data[-1]  # Combine if order no is split
                    product_info["sku"] = " ".join(flat_data[:-5])


        # Clean up extracted data
        for key in product_info:
            if isinstance(product_info[key], str):
                product_info[key] = product_info[key].strip()

    except Exception as e:
        print(f"❌ Product parsing error: {e}")
        print(f"Block text sample: {block_text[:500]}")

    return product_info