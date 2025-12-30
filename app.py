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


#“ה־http_exception_handler מאפשר טיפול מרכזי ואחיד בשגיאות HTTP, בלי לחזור על אותו קוד בכל endpoint.”
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
    # (4) 503
    try:
        response = doc_client.analyze_document(request)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The service is currently unavailable. Please try again later."
        )
    data = {}
    data_confidence = {} 
    confidence = 0.0

    for page in (response.data.pages or []):
        for field in (getattr(page, "document_fields", None) or []):
            label = getattr(field, "field_label", None)
            field_name = getattr(label, "name", None)
            field_confidence = getattr(label, "confidence", None)

            field_value = getattr(field, "field_value", None)
            field_value_text = getattr(field_value, "text", None) 

            if field.field_type == "LINE_ITEM_GROUP":
                items = []
                rows = getattr(field_value, "items", None) or [] #כל השורות של ה־ Items בתוך החשבונית

                for row in rows: #
                    item = {
                        "Description": None,
                        "Name": None,
                        "Quantity": None,
                        "UnitPrice": None,
                        "Amount": None,
                    }

                    row_value_obj = getattr(row, "field_value", None) #הערכים של הפריט
                    cols = getattr(row_value_obj, "items", None) or [] #כל העמודות/השדות של הפריט

                    for c in cols: 
                        c_label = getattr(c, "field_label", None) 
                        c_conf = getattr(c_label, "confidence", None)
                        k = getattr(c_label, "name", None) #שם השדה בעמודה
                        v_obj = getattr(c, "field_value", None) #הערך של השדה בעמודה
                        v = getattr(v_obj, "text", None) if v_obj else None #הטקסט של הערך בעמודה

                        # ניקוי ערכים מספריים
                        if k in ("UnitPrice", "Amount"):
                            v = clean_money(v)
                        elif k == "Quantity":
                            v = int(clean_money(v)) if clean_money(v) is not None else None

                        if k in item:
                            item[k] = v #הכנסת הערך המתאים לשדה המתאים במילון הפריט  

                    items.append(item) # הוספת הפריט לרשימת הפריטים

                data["Items"] = items

            elif field_name: # אם יש שם שדה תקין
                v = field_value_text #הטקסט של הערך של השדה

                money_fields = {"SubTotal", "ShippingCost", "InvoiceTotal", "AmountDue"}
                if field_name in money_fields and v:
                    v = clean_money(v)

                data[field_name] = v
                data_confidence[field_name] = field_confidence

    if response.data.detected_document_types:
        for doc_type in response.data.detected_document_types:
            confidence = doc_type.confidence if doc_type.confidence is not None else 0.0
   
    # continue (3) 400
    if confidence < 0.9:
        raise HTTPException(
            status_code=400,
            detail="Invalid document. Please upload a valid PDF invoice with high confidence."
        )

    result = {
        "confidence": confidence,
        "data": data,
        "dataConfidence": data_confidence,
    }

    save_inv_extraction(result)
    return result


@app.get('/health')
def health():
    return {"status": "ok"}


@app.get('/invoice/{invoice_id}')
def get_invoice_by_id(invoice_id: str):
    with get_db() as conn: #ניהול חיבור לבסיס הנתונים
        cursor = conn.cursor() #מצביע (cursor) שרץ על מסד הנתונים ומבצע פקודות SQL

        cursor.execute("""
            SELECT InvoiceId, VendorName, InvoiceDate, BillingAddressRecipient,
                   ShippingAddress, SubTotal, ShippingCost, InvoiceTotal
            FROM invoices
            WHERE InvoiceId = ? 
        """, (invoice_id,)) #,כי SQLite מצפה ל־ tuple/ של פרמטרים ? = אבטחה ויציבות
       
        row = cursor.fetchone() #Tuple
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
