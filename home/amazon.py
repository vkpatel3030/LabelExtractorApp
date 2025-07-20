from django.shortcuts import render
from django.http import FileResponse
import fitz  # PyMuPDF
import pandas as pd
import re
import os
import tempfile
from datetime import datetime

def extract_amazon_table_data(text):
    table_data = []
    pattern = re.compile(
        r"(\d+)\s+"  # SI No
        r"(.*?)\s*"
        r"\|\s*B0\w+\s*\([^)]+\)\s*"
        r"HSN:\d+\s*"
        r"₹([\d,]+\.\d{2})\s*"
        r"(?:-₹([\d,]+\.\d{2})\s*)?"
        r"(\d+)\s*"
        r"₹([\d,]+\.\d{2})\s*"
        r"(\d+%)\s*"
        r"(IGST|CGST|SGST)\s*"
        r"₹([\d,]+\.\d{2})\s*"
        r"₹([\d,]+\.\d{2})",
        re.DOTALL
    )

    for match in pattern.finditer(text):
        table_data.append({
            "SI No": match.group(1),
            "Description": match.group(2).replace('\n', ' ').strip(),
            "Unit Price": match.group(3),
            "Discount": match.group(4) if match.group(4) else "₹0.00",
            "Qty": match.group(5),
            "Net Amount": match.group(6),
            "Tax Rate": match.group(7),
            "Tax Type": match.group(8),
            "Tax Amount": match.group(9),
            "Total Amount": match.group(10),
        })

    return table_data


def amazonindex(request):
    message = None
    extracted_data_for_display = []
    output_filename = None

    if request.method == "POST" and request.FILES.get("pdf_file"):
        uploaded_file = request.FILES["pdf_file"]

        # ✅ Save uploaded file to /tmp (Vercel-compatible)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir="/tmp") as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            full_file_path = tmp.name

        doc = None
        try:
            doc = fitz.open(full_file_path)
            extracted_labels = []

            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                block = page.get_text("text")

                order_id = invoice_no = order_date = invoice_date = ""
                buyer_name = address = pincode = ""
                gstin = awb_number = weight = ""
                pickup_partner = "Amazon Transportation"

                awb_match = re.search(r"\bAWB\s+([A-Z0-9]{10,})", block)
                if awb_match:
                    awb_number = awb_match.group(1).strip()

                weight_match = re.search(r"\b(?:Weight|Wt\.?)\s*[:\-]?\s*(\d+\.?\d*)\s*(?:kg|kgs)", block, re.IGNORECASE)
                if weight_match:
                    weight = weight_match.group(1).strip()

                order_match = re.search(r"Order Number:\s*(\d{3}-\d{7}-\d{7})", block)
                if order_match:
                    order_id = order_match.group(1)

                invoice_match = re.search(r"Invoice Number\s*:\s*([A-Z0-9\-]+)", block)
                if invoice_match:
                    invoice_no = invoice_match.group(1)

                order_date_match = re.search(r"Order Date:\s*(\d{2}\.\d{2}\.\d{4})", block)
                if order_date_match:
                    try:
                        order_date = datetime.strptime(order_date_match.group(1), "%d.%m.%Y").strftime("%d/%m/%Y")
                    except:
                        order_date = order_date_match.group(1)

                invoice_date_match = re.search(r"Invoice Date\s*:\s*(\d{2}\.\d{2}\.\d{4})", block)
                if invoice_date_match:
                    try:
                        invoice_date = datetime.strptime(invoice_date_match.group(1), "%d.%m.%Y").strftime("%d/%m/%Y")
                    except:
                        invoice_date = invoice_date_match.group(1)

                gstin_match = re.search(r"GST Registration No:\s*([A-Z0-9]+)", block)
                if gstin_match:
                    gstin = gstin_match.group(1)

                ship_match = re.search(r"Shipping Address\s*:\s*(.*?)(?:Place of supply:|State/UT Code:|\Z)", block, re.DOTALL)
                if ship_match:
                    lines = [l.strip() for l in ship_match.group(1).split('\n') if l.strip()]
                    if lines:
                        buyer_name = lines[0]
                        rest = "\n".join(lines[1:])
                        pin = re.search(r"(\d{6})", rest)
                        if pin:
                            pincode = pin.group(1)
                            address = rest.replace(pincode, "").strip()

                # Extract product rows
                product_rows = extract_amazon_table_data(block)

                for row in product_rows:
                    extracted_labels.append({
                        "Order ID": order_id,
                        "Order Date": order_date,
                        "Invoice No": invoice_no,
                        "Invoice Date": invoice_date,
                        "Buyer Name": buyer_name,
                        "Address": address,
                        "Pincode": pincode,
                        "GSTIN": gstin,
                        "AWB Number": awb_number,
                        "Pickup Partner": pickup_partner,
                        "Weight": weight,
                        "SI No": row["SI No"],
                        "Description": row["Description"],
                        "Unit Price": row["Unit Price"],
                        "Discount": row["Discount"],
                        "Qty": row["Qty"],
                        "Net Amount": row["Net Amount"],
                        "Tax Rate": row["Tax Rate"],
                        "Tax Type": row["Tax Type"],
                        "Tax Amount": row["Tax Amount"],
                        "Total Amount": row["Total Amount"]
                    })

            df = pd.DataFrame(extracted_labels)

            if df.empty:
                message = "❌ No data extracted from PDF"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"amazon_invoice_{timestamp}.xlsx"
                tmp_file_path = os.path.join("/tmp", output_filename)
                df.to_excel(tmp_file_path, index=False)

                message = f"✅ {len(df)} rows extracted successfully."
                extracted_data_for_display = df.to_dict(orient="records")

                return FileResponse(open(tmp_file_path, 'rb'), as_attachment=True, filename=output_filename)

        except Exception as e:
            message = f"❌ Error: {str(e)}"
        finally:
            if doc:
                doc.close()
            if os.path.exists(full_file_path):
                os.remove(full_file_path)

    return render(request, "upload_file.html", {
        "message": message,
        "extracted_data": extracted_data_for_display,
        "output_filename": output_filename
    })
