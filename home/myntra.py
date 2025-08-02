from django.shortcuts import render
from django.core.files.storage import default_storage
import fitz  # PyMuPDF
import pandas as pd
import re
import os
import tempfile
from datetime import datetime
from django.http import FileResponse

def myntraindex(request):
    message = None
    if request.method == "POST" and request.FILES.get("pdf_file"):
        uploaded_file = request.FILES["pdf_file"]
        temp_file_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)

        # ✅ PDF Temporary Save
        with open(temp_file_path, 'wb+') as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)

        try:
            # ✅ PDF Read
            doc = fitz.open(temp_file_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()
            print("Extracted Data:", extracted_data)
            print("Full Text Sample:", full_text[:2000])


            # ✅ Extract Data
            extracted_data = extract_myntra_labels(full_text)

            if extracted_data:
                df = pd.DataFrame(extracted_data)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", dir=tempfile.gettempdir()) as tmp_file:
                    df.to_excel(tmp_file.name, index=False)
                    tmp_file.flush()
                    tmp_file_path = tmp_file.name

                message = f"✅ {len(extracted_data)} labels extracted successfully."
                return FileResponse(open(tmp_file_path, 'rb'), as_attachment=True, filename="myntra_labels.xlsx")

            else:
                message = "❌ No label data found in PDF."

        except Exception as e:
            message = f"❌ Error: {str(e)}"

        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return render(request, "upload_file.html", {"message": message})


def extract_myntra_labels(full_text):
    """📦 Extract Myntra label details"""
    label_blocks = full_text.split("Customer Address")
    extracted = []

    for block in label_blocks[1:]:
        block_text = "Customer Address" + block

        # ✅ Extract Fields
        customer_address = extract_customer_address(block_text)
        order_date = extract_order_date(block_text)
        invoice_date = extract_invoice_date(block_text)
        gstin = extract_gstin(block_text)
        awb = extract_awb(block_text)
        pickup = extract_pickup(block_text)
        product_info = extract_product_info(block_text)

        extracted.append({
            "SKU": product_info.get("sku", ""),
            "Size": product_info.get("size", ""),
            "Qty": product_info.get("qty", ""),
            "Color": product_info.get("color", ""),
            "Order No.": product_info.get("order_no", ""),
            "Order Date": order_date,
            "Invoice Date": invoice_date,
            "GSTIN": gstin,
            "AWB Number": awb,
            "Pickup": pickup,
            "Customer Address": customer_address
        })

    return extracted


# ✅ Helper Functions (Same as Meesho)
def extract_customer_address(text):
    match = re.search(
        r"Customer Address\s*\n(.+?)(?:If undelivered|Prepaid|Invoice|Order|SKU)",
        text, re.DOTALL | re.IGNORECASE
    )
    if match:
        lines = [l.strip() for l in match.group(1).strip().split("\n") if l.strip()]
        return ", ".join(lines)
    return ""

def extract_order_date(text):
    patterns = [
        r"Order\s*Date\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        r"Dispatch\s*on\s*(\d{2}-\d{2}-\d{4})"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""

def extract_invoice_date(text):
    patterns = [r"Invoice\s*Date\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})"]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def extract_gstin(text):
    m = re.search(r"GSTIN\s*[:\-]?\s*([0-9A-Z]{15})", text)
    return m.group(1) if m else ""


def extract_awb(text):
    m = re.search(r"(?:AWB|Tracking)\s*(?:No\.?|Number)?[:\-]?\s*([A-Z0-9]{8,20})", text, re.IGNORECASE)
    return m.group(1) if m else ""


def extract_pickup(text):
    couriers = ["Delhivery", "XpressBees", "Ekart", "Ecom Express", "Shadowfax", "DTDC", "Blue Dart"]
    for c in couriers:
        if re.search(rf"\b{c}\b", text, re.IGNORECASE):
            return c
    return ""


def extract_product_info(text):
    sku = size = qty = color = ""
    lines = text.splitlines()

    for line in lines:
        if re.search(r"SKU.*Size.*Qty", line, re.IGNORECASE):
            continue
        if re.match(r"\S+", line) and len(line.split()) >= 4:
            parts = line.split()
            sku = " ".join(parts[:-3])  # SKUમાં આખું value
            size, qty, color = parts[-3:]
            break

    return {"sku": sku, "size": size, "qty": qty, "color": color}

    if product_lines:
        parts = product_lines[0].split()
        if len(parts) >= 5:
            product_info["sku"] = " ".join(parts[:-4])
            product_info["size"] = parts[-4]
            product_info["qty"] = parts[-3]
            product_info["color"] = parts[-2]
            product_info["order_no"] = parts[-1]

    return product_info