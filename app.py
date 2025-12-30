from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
import oci
import base64
import re
from db_util import get_db, init_db, save_inv_extraction
import time
app = FastAPI()

config = oci.config.from_file()
doc_client = oci.ai_document.AIServiceDocumentClient(config)


#היא נרשמת אוטומטית כ־“handler” לכל שגיאות מהסוג הזה (HTTPException).
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)}
    )


# אם הקובץ PDF תקין
def is_pdf(upload: UploadFile, content: bytes) -> bool:
    return (
        (upload.content_type == "application/pdf"
         or (upload.filename and upload.filename.lower().endswith(".pdf")))
        and content.startswith(b"%PDF-")
    )


# ניקוי ערכים מ $, רווחים וכו'ומחזיומחיר float
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

    before = time.time()
    # (4) 503
    try:
        response = doc_client.analyze_document(request)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The service is currently unavailable. Please try again later."
        )
    after = time.time()
    prediction_time = round(after - before, 3)
    data = {}
    data_confidence = {}   # שקיפות ושליטה ברמת שדה בודד
    all_confidences = []   # לחשב את רמת הביטחון הכוללת למסמך
    overall_confidence = 0.0

    for page in (response.data.pages or []):
        for field in (getattr(page, "document_fields", None) or []):

            # גישה בטוחה ל-label
            label = getattr(field, "field_label", None)
            field_name = getattr(label, "name", None)
            field_confidence = getattr(label, "confidence", None)

            field_value_obj = getattr(field, "field_value", None)
            field_value = getattr(field_value_obj, "text", None) if field_value_obj else None

            if field.field_type == "LINE_ITEM_GROUP":
                items = []
                rows = getattr(field_value_obj, "items", None) or []

                for row in rows:
                    item = {
                        "Description": None,
                        "Name": None,
                        "Quantity": None,
                        "UnitPrice": None,
                        "Amount": None,
                    }

                    row_value_obj = getattr(row, "field_value", None)
                    cols = getattr(row_value_obj, "items", None) or []

                    for c in cols:
                        # ✅ כאן היה הכשל אצלך: לא נוגעים ב-confidence בלי getattr
                        c_label = getattr(c, "field_label", None)
                        c_conf = getattr(c_label, "confidence", None)
                        if c_conf is not None:
                            all_confidences.append(c_conf)

                        k = getattr(c_label, "name", None)
                        v_obj = getattr(c, "field_value", None)
                        v = getattr(v_obj, "text", None) if v_obj else None

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

                # כל השדות הכספיים/מספריים שצריכים להיות float (כמו שהטסט מצפה)
                money_fields = {"SubTotal", "ShippingCost", "InvoiceTotal", "AmountDue"}
                if field_name in money_fields and v:
                    v = clean_money(v)

                data[field_name] = v
                data_confidence[field_name] = field_confidence

                if field_confidence is not None:
                    all_confidences.append(field_confidence)
    if response.data.detected_document_types:
        for doc_type in response.data.detected_document_types:
            overall_confidence = doc_type.confidence if doc_type.confidence is not None else 0.0
   
    # continue (3) 400
    if overall_confidence < 0.9:
        raise HTTPException(
            status_code=400,
            detail="Invalid document. Please upload a valid PDF invoice with high confidence."
        )

    result = {
        "confidence": overall_confidence,
        "data": data,
        "dataConfidence": data_confidence,
        "predictionTime": prediction_time,
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
async def invoices_by_vendor(vendor_name: str):
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


def get_invoices_by_vendor(vendor_name: str):
    with get_db() as conn:
        cursor = conn.cursor()

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
