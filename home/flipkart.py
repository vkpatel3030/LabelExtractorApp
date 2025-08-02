from django.shortcuts import render
from django.core.files.storage import default_storage
import fitz
import pandas as pd
import re
import os
import tempfile 
from datetime import datetime
from django.http import FileResponse

def flipkartindex(request):
    message = None
    extracted_data_for_display = []

    if request.method == "POST" and request.FILES.get("pdf_file"):
        uploaded_file = request.FILES["pdf_file"]
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_file.flush()
            file_path = tmp_file.name    
        try:
            doc = fitz.open(file_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text("text") + "\n"
            doc.close()

            split_pattern = r"(OD\d{17,20})"
            parts = re.split(split_pattern, full_text)
            extracted_labels = []

            for i in range(1, len(parts), 2):
                current_order_id = parts[i].strip()
                current_block_content = parts[i+1].strip() if (i+1) < len(parts) else ""
                block = current_order_id + "\n" + current_block_content

                order_id = current_order_id
                sku_id = ""
                description = ""
                qty = ""
                pickup_partner = "Ekart Logistics"
                hbd = ""
                cpd = ""
                awb_no = ""
                gstin = ""
                customer_address = ""
                pincode = ""
                print_data = ""

                # SKU and Description
                sku_desc_match = re.search(r"SKU ID\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$|\s{2,})", block, re.DOTALL | re.IGNORECASE)
                if sku_desc_match:
                    sku_id = sku_desc_match.group(1).strip()
                    sku_id = re.sub(r"(?i)description\s*QTY\s*\d+\s*", "", sku_id).strip()
                    sku_id = re.sub(r"(?i)QTY\s*\d+\s*", "", sku_id).strip()
                    description = sku_desc_match.group(2).strip().replace("\n", " ")
                else:
                    sku_id_match = re.search(r"SKU ID\s*[:=]\s*(.+?)(?:\||\n|\r|\s{2,})", block, re.IGNORECASE)
                    if sku_id_match:
                        sku_id = sku_id_match.group(1).strip()
                        sku_id = re.sub(r"(?i)description\s*QTY\s*\d+\s*", "", sku_id).strip()
                        sku_id = re.sub(r"(?i)QTY\s*\d+\s*", "", sku_id).strip()

                    desc_match = re.search(r"(?:Description\s*[:=]?\s*|SKU ID\s*\|\s*.+?\|\s*)(.+?)(?=\n\s*QTY|\n\s*FMPC|\n\s*FMPP|\n\s*Tax|\n\s*Order\s*Id:|\n\s*AWB\s*No\.?|\n\s*HBD:|\n\s*CPD:|$)", block, re.DOTALL | re.IGNORECASE)
                    if desc_match:
                        description = desc_match.group(1).strip().replace("\n", " ")
                        if sku_id and description.startswith(sku_id):
                            description = description[len(sku_id):].strip()
                            if description.startswith('|'):
                                description = description[1:].strip()

                qty_match = re.search(r"QTY\s*(\d+)", block, re.IGNORECASE)
                if qty_match:
                    qty = qty_match.group(1).strip()

                hbd_match = re.search(r"HBD:\s*(\d{2}\s*-\s*\d{2})", block, re.IGNORECASE)
                if hbd_match:
                    hbd = hbd_match.group(1).replace(" ", "").strip()

                cpd_match = re.search(r"CPD:\s*(\d{2}\s*-\s*\d{2})", block, re.IGNORECASE)
                if cpd_match:
                    cpd = cpd_match.group(1).replace(" ", "").strip()

                awb_match = re.search(r"AWB\s*No\.?\s*([A-Z0-9]+)", block, re.IGNORECASE)
                if awb_match:
                    awb_no = awb_match.group(1).strip()

                gstin_match = re.search(r"GSTIN:\s*([A-Z0-9]+)", block, re.IGNORECASE)
                if gstin_match:
                    gstin = gstin_match.group(1).strip()

                printed_match = re.search(r"Printed at\s+\d{3,4}\s*hrs,\s*(\d{2}/\d{2}/\d{2})", block, re.IGNORECASE)
                if printed_match:
                    print_data = printed_match.group(1).strip()

                address_start_pattern = r"Shipping/Customer address:\s*Name:\s*(.+?)\n"
                address_end_patterns = r"(?:HBD:|Sold By:|GSTIN:)"
                address_block_match = re.search(f"{address_start_pattern}(.*?)(?={address_end_patterns})", block, re.DOTALL | re.IGNORECASE)

                if address_block_match:
                    name = address_block_match.group(1).strip()
                    address_lines_raw = address_block_match.group(2).strip()
                    cleaned_address_lines = [line.strip() for line in address_lines_raw.split('\n') if line.strip()]
                    full_address = f"{name}, " + ", ".join(cleaned_address_lines)

                    pincode_match = re.search(r"(.*?\b(\d{6})\b)", full_address)
                    if pincode_match:
                        customer_address = pincode_match.group(1).strip()
                        pincode = pincode_match.group(2)
                    else:
                        customer_address = full_address.strip()
                else:
                    simple_address_match = re.search(r"Shipping/Customer address:\s*Name:\s*(.+?)(?=\n\n|\n\s*HBD:|\n\s*Sold By:|\n\s*GSTIN:)", block, re.DOTALL | re.IGNORECASE)
                    if simple_address_match:
                        full_address = simple_address_match.group(1).strip().replace("\n", ", ")
                        pincode_match = re.search(r"(.*?\b(\d{6})\b)", full_address)
                        if pincode_match:
                            customer_address = pincode_match.group(1).strip()
                            pincode = pincode_match.group(2)
                        else:
                            customer_address = full_address.strip()

                if order_id or sku_id:
                    extracted_labels.append({
                        "Order ID": order_id,
                        "SKU ID": sku_id,
                        "Description": description,
                        "QTY": qty,
                        "Print Data": print_data,
                        "Pickup Partner": pickup_partner,
                        "HBD": hbd,
                        "CPD": cpd,
                        "AWB No.": awb_no,
                        "GSTIN": gstin,
                        "Shipping/Customer address": customer_address,
                        "Pincode": pincode
                    })

            df = pd.DataFrame(extracted_labels)

            if df.empty:
                message = "\u274c PDF se koi label data nahi nikala gaya."
            else:
                columns_order = [
                    "Order ID", "SKU ID", "Description", "QTY", "Print Data", "Pickup Partner",
                    "HBD", "CPD", "AWB No.", "GSTIN", "Shipping/Customer address", "Pincode"
                ]
                df = df.reindex(columns=columns_order, fill_value="")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = "flipkart_labels_" + timestamp + ".xlsx"
                output_filename = f"flipkart_labels_{timestamp}.xlsx"
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_excel:
                    df.to_excel(tmp_excel.name, index=False)
                    tmp_excel.flush()
                    output_path = tmp_excel.name
                
                message = f"\u2705 {len(df)} labels extracted and saved to: /{output_path}"
                extracted_data_for_display = df.to_dict(orient='records')
                response = FileResponse(open(output_path, 'rb'), as_attachment=True, filename=os.path.basename(output_path))
                return response

        except fitz.FileDataError:
            message = "\u274c Invalid or corrupted PDF file."
        except Exception as e:
            message = f"\u274c Unexpected error: {str(e)}"
        finally:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except:
                pass
    return render(request, "upload_file.html", {
        "message": message,
        "extracted_data": extracted_data_for_display
    })
