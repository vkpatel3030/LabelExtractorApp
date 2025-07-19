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

        print(f"📥 Uploaded file: {uploaded_file.name}")
        print(f"📍 Saving to temp path: {temp_file_path}")

        with open(temp_file_path, 'wb+') as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)

        try:
            extracted_data = []
            chunks = split_pdf_chunks(temp_file_path, pages_per_chunk=10)

            for i, sub_doc in enumerate(chunks):
                print(f"📖 Reading text from chunk {i + 1}")
                full_text = ""
                for page in sub_doc:
                    try:
                        full_text += page.get_text()
                    except Exception as e:
                        print(f"❌ Error reading page: {e}")
                sub_doc.close()

                label_blocks = full_text.split("Customer Address")
                print(f"🔍 Found {len(label_blocks) - 1} blocks in chunk {i + 1}")
                for block_index, block in enumerate(label_blocks[1:]):
                    try:
                        block_text = "Customer Address" + block

                        customer_address = extract_customer_address(block_text)
                        order_date = extract_order_date(block_text)
                        invoice_date = extract_invoice_date(block_text)
                        gstin = extract_gstin(block_text)
                        awb_number = extract_awb_number(block_text)
                        pickup = extract_pickup_partner(block_text)
                        product_info = extract_product_info(block_text)

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
                    except Exception as e:
                        print(f"Error processing block {block_index + 1} in chunk {i + 1}: {e}")

            if extracted_data:
                df = pd.DataFrame(extracted_data)[[
                    "SKU", "Size", "Qty", "Color", "Order No.",
                    "Order Date", "Invoice Date", "GSTIN",
                    "AWB Number", "Pickup", "Customer Address"
                ]]

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", dir=tempfile.gettempdir()) as tmp_file:
                    df.to_excel(tmp_file.name, index=False)
                    tmp_file.flush()
                    tmp_file_path = tmp_file.name

                print(f"✅ Excel file created: {tmp_file_path}")
                message = f"✅ {len(extracted_data)} labels extracted and saved."
                response = FileResponse(open(tmp_file_path, 'rb'), as_attachment=True, filename=os.path.basename(tmp_file_path))
                return response
            else:
                message = "No data extracted from PDF"
                print("No labels found in any chunk")

        except Exception as e:
            message = f"Error processing PDF: {str(e)}"
            print(message)
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                print("Temp PDF file removed")

    return render(request, "upload_file.html", {"message": message})