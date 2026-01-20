from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import oci
import base64
import re

from db import get_db, get_db_session
from helpers import is_pdf, clean_money
import queries
from db_util import init_db, DbUnit_save_inv_extraction
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://172.18.224.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_oci_client():  # pragma: no cover
    config = oci.config.from_file()
    doc_client = oci.ai_document.AIServiceDocumentClient(config)
    return doc_client


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
    )

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    pdf_bytes = await file.read()

    if not pdf_bytes or not is_pdf(file, pdf_bytes):
        raise HTTPException(
            status_code=400,
            detail="Invalid document. Please upload a valid PDF invoice with high confidence.",
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

    try:
        response = get_oci_client().analyze_document(request)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The service is currently unavailable. Please try again later.",
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
                rows = getattr(field_value, "items", None) or []

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
                        c_label = getattr(c, "field_label", None)
                        k = getattr(c_label, "name", None)
                        v_obj = getattr(c, "field_value", None)
                        v = getattr(v_obj, "text", None) if v_obj else None

                        if k in ("UnitPrice", "Amount"):
                            v = clean_money(v)
                        elif k == "Quantity":
                            q = clean_money(v)
                            v = int(q) if q is not None else None

                        if k in item:
                            item[k] = v

                    items.append(item)

                data["Items"] = items

            elif field_name:
                v = field_value_text
                money_fields = {"SubTotal", "ShippingCost", "InvoiceTotal", "AmountDue"}
                if field_name in money_fields and v:
                    v = clean_money(v)

                data[field_name] = v
                data_confidence[field_name] = field_confidence

    if response.data.detected_document_types:
        for doc_type in response.data.detected_document_types:
            confidence = doc_type.confidence if doc_type.confidence is not None else 0.0

    if confidence < 0.9:
        raise HTTPException(
            status_code=400,
            detail="Invalid document. Please upload a valid PDF invoice with high confidence.",
        )

    result = {
        "confidence": confidence,
        "data": data,
        "dataConfidence": data_confidence,
    }

    DbUnit_save_inv_extraction(result)
    return result


@app.get("/invoice/{invoice_id}")
def get_invoice(invoice_id: str, db: Session = Depends(get_db_session)):
    invoice = queries.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = {
        "InvoiceId": invoice.InvoiceId,
        "VendorName": invoice.VendorName,
        "InvoiceDate": invoice.InvoiceDate,
        "BillingAddressRecipient": invoice.BillingAddressRecipient,
        "ShippingAddress": invoice.ShippingAddress,
        "SubTotal": invoice.SubTotal,
        "ShippingCost": invoice.ShippingCost,
        "InvoiceTotal": invoice.InvoiceTotal,
        "Items": [
            {
                "Description": it.Description,
                "Name": it.Name,
                "Quantity": it.Quantity,
                "UnitPrice": it.UnitPrice,
                "Amount": it.Amount,
            }
            for it in (invoice.items or [])
        ],
    }
    return result


@app.get("/invoices/vendor/{vendor_name}")
def invoices_by_vendor(vendor_name: str, db: Session = Depends(get_db_session)):
    invoices = queries.get_invoices_by_vendor(db, vendor_name)

    if not invoices:
        return {"VendorName": "Unknown Vendor", "TotalInvoices": 0, "invoices": []}

    result = {
        "VendorName": vendor_name,
        "TotalInvoices": len(invoices),
        "invoices": [
            {
                "InvoiceId": inv.InvoiceId,
                "VendorName": inv.VendorName,
                "InvoiceDate": inv.InvoiceDate,
                "BillingAddressRecipient": inv.BillingAddressRecipient,
                "ShippingAddress": inv.ShippingAddress,
                "SubTotal": inv.SubTotal,
                "ShippingCost": inv.ShippingCost,
                "InvoiceTotal": inv.InvoiceTotal,
                "Items": [
                    {
                        "Description": it.Description,
                        "Name": it.Name,
                        "Quantity": it.Quantity,
                        "UnitPrice": it.UnitPrice,
                        "Amount": it.Amount,
                    }
                    for it in (inv.items or [])
                ],
            }
            for inv in invoices
        ],
    }
    return result


if __name__ == "__main__":  
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8080)
