from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
import oci
import base64
import re
from db_util import get_db, init_db, save_inv_extraction

"""
echo "[" > all_invoices.json
first=1

for f in invoices_sample/*.pdf; do
  [ $first -eq 0 ] && echo "," >> all_invoices.json
  first=0

  curl -s -X POST "http://127.0.0.1:8080/extract" \
       -F "file=@$f" >> all_invoices.json
done

echo "]" >> all_invoices.json

python -m json.tool all_invoices.json > tmp.json && mv tmp.json all_invoices.json
"""
"""
for f in invoices_sample/*.pdf; do
  echo "Sending $f"
  curl -X POST "http://127.0.0.1:8080/extract" -F "file=@$f"
  echo ""
done
"""    

app = FastAPI()

config = oci.config.from_file()
doc_client = oci.ai_document.AIServiceDocumentClient(config)

#טיפול בשגיאות HTTP
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)}
    )

#אם הקובץ PDF תקין
def is_pdf(upload: UploadFile, content: bytes) -> bool:
    return (
        (upload.content_type == "application/pdf"
         or (upload.filename and upload.filename.lower().endswith(".pdf")))
        and content.startswith(b"%PDF-")
    )

# ניקוי ערכים מ $, רווחים וכו'
def clean_money(value: str):
    if not value:
        return None
    v = re.sub(r"[^\d.]", "", value)
    return float(v) if v else None



@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    # (3) 400
    if not pdf_bytes or not is_pdf(file, pdf_bytes):
            raise HTTPException(
                status_code=400,
                detail="Invalid document. Please upload a valid PDF invoice with high confidence."
            )

    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    document = oci.ai_document.models.InlineDocumentDetails(data=encoded_pdf)

    request = oci.ai_document.models.AnalyzeDocumentDetails(
        document=document,
        features=[
            oci.ai_document.models.DocumentFeature(feature_type="KEY_VALUE_EXTRACTION"),
            oci.ai_document.models.DocumentClassificationFeature(max_results=5),
        ],
    )
    # (4) 503
    try:
        response = doc_client.analyze_document(request)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The service is currently unavailable. Please try again later."
        )

    data = {}
    data_confidence = {} #שקיפות ושליטה ברמת שדה בודד
    all_confidences = [] #לחשב את רמת הביטחון הכוללת למסמך  

    for page in response.data.pages: # for page in (response.data.pages or []):
        if page.document_fields:
            for field in page.document_fields:
                label = getattr(field, "field_label", None)
                field_name = getattr(label, "name", None)
                field_confidence = getattr(label, "confidence", None)

                field_value = (
                    getattr(field.field_value, "text", None)
                    if getattr(field, "field_value", None)
                    else None
                )

                if field.field_type == "LINE_ITEM_GROUP":
                    items = []
                    rows = field.field_value.items if field.field_value else [] # שורות של כל הפריטים

                    for row in rows: # עבור כל שורה בטבלה
                        item = {
                            "Description": None,
                            "Name": None,
                            "Quantity": None,
                            "UnitPrice": None,
                            "Amount": None,
                        }

                        cols = row.field_value.items if row.field_value else [] # עמודות / שדות של כל שורה בתוך כל Item
                        for c in cols:
                            c_label = getattr(c, "field_label", None)
                            c_conf = getattr(c_label, "confidence", None)

                            if c_conf is not None:
                                all_confidences.append(c_conf)

                            k = getattr(c_label, "name", None)                 # במקום c.field_label.name
                            v_obj = getattr(c, "field_value", None)
                            v = getattr(v_obj, "text", None) if v_obj else None  # במקום c.field_value.text

                            # ניקוי ערכים מספריים
                            if k in ("Quantity", "UnitPrice", "Amount") and v:
                                v2 = re.sub(r"[^\d.]", "", v)
                                v = float(v2) if v2 else None

                            if k in item:
                                item[k] = v

                        items.append(item)

                    data["Items"] = items

                elif field_name:
                    v = field_value
                    if field_name in ("AmountDue", "InvoiceTotal") and v:
                        v = clean_money(v)
                    data[field_name] = v
                    data_confidence[field_name] = field_confidence

                    if field_confidence is not None:
                        all_confidences.append(field_confidence)

   # overall_confidence = round(sum(all_confidences) / len(all_confidences), 3) if all_confidences else 0.0
    if response.data.detected_document_types:
        for doc_type in response.data.detected_document_types:
            overall_confidence = doc_type.confidence if doc_type.confidence is not None else 0.0
    #continue (3) 400
    if overall_confidence < 0.9:
        raise HTTPException(status_code=400,detail=("Invalid document. Please upload a valid PDF invoice with high confidence."))

    result = {
        "confidence": overall_confidence,
        "data": data,
        "dataConfidence": data_confidence
    }   
    save_inv_extraction(result)
    return result


@app.get('/health')
def health():
    return {"status": "ok"} 


@app.get('/invoice/{invoice_id}')

def get_invoice_by_id(invoice_id: str):
    with get_db() as conn:
        cursor = conn.cursor()

        # ✅ SELECT invoice header
        cursor.execute("""
            SELECT InvoiceId, VendorName, InvoiceDate, BillingAddressRecipient,
                   ShippingAddress, SubTotal, ShippingCost, InvoiceTotal
            FROM invoices
            WHERE InvoiceId = ?
        """, (invoice_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Invoice not found")

        invoice = {
            "InvoiceId": row[0],
            "VendorName": row[1],
            "InvoiceDate": row[2],
            "BillingAddressRecipient": row[3],
            "ShippingAddress": row[4],
            "SubTotal": row[5],
            "ShippingCost": row[6],
            "InvoiceTotal": row[7],
        }

        # ✅ SELECT line items
        cursor.execute("""
            SELECT Description, Name, Quantity, UnitPrice, Amount
            FROM items
            WHERE InvoiceId = ?
            ORDER BY id ASC
        """, (invoice_id,))
        items_rows = cursor.fetchall()

        invoice["Items"] = [
            {
                "Description": r[0],
                "Name": r[1],
                "Quantity": r[2],
                "UnitPrice": r[3],
                "Amount": r[4],
            }
            for r in items_rows
        ]
        
        return invoice


@app.get("/invoices/vendor/{vendor_name}")
async def invoices_by_vendor(vendor_name: str): #שכבת API: פורמט תשובה, קודי שגיאה, מבנה JSON שהמרצה רוצה
    invoices = get_invoices_by_vendor(vendor_name)

    if not invoices:
        return {
            "VendorName": "Unknown Vendor",
            "TotalInvoices": 0,
            "invoices": []
        }

    return {
        "VendorName": vendor_name,
        "TotalInvoices": len(invoices),
        "invoices": invoices
    }


def get_invoices_by_vendor(vendor_name: str): #שכבת DB: רק SQL והחזרת נתונים מבנה נתונים פנימי
    with get_db() as conn:
        cursor = conn.cursor()

        # ✅ SELECT all invoice ids for vendor
        cursor.execute("""
            SELECT InvoiceId
            FROM invoices
            WHERE VendorName = ?
            ORDER BY InvoiceDate ASC
        """, (vendor_name,))
        invoice_ids = [r[0] for r in cursor.fetchall()]

    invoices = []
    for inv_id in invoice_ids:
        inv = get_invoice_by_id(inv_id)
        if inv:
            invoices.append(inv)

    return invoices

if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8080)
