from fastapi import FastAPI, UploadFile, File
import oci, base64, re
from db_util import init_db
import json, os, time

app = FastAPI()

config = oci.config.from_file()
client = oci.ai_document.AIServiceDocumentClient(config)


def text(v):
    return getattr(v, "text", None) if v else None


def num(v):
    if not v:
        return None
    v = re.sub(r"[^\d.,]", "", v).replace(",", ".")
    try:
        return float(v)
    except:
        return None


def parse_items(f):
    items = []
    rows = getattr(f.field_value, "items", []) if f.field_value else []
    for r in rows:
        cols = {c.field_label.name: c for c in r.field_value.items}
        items.append({
            "Description": text(cols.get("Description").field_value) if "Description" in cols else None,
            "Name": text(cols.get("Name").field_value) if "Name" in cols else None,
            "Quantity": num(text(cols.get("Quantity").field_value)) if "Quantity" in cols else None,
            "UnitPrice": num(text(cols.get("UnitPrice").field_value)) if "UnitPrice" in cols else None,
            "Amount": num(text(cols.get("Amount").field_value)) if "Amount" in cols else None
        })
    return items


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    pdf = base64.b64encode(await file.read()).decode()
    req = oci.ai_document.models.AnalyzeDocumentDetails(
        document=oci.ai_document.models.InlineDocumentDetails(data=pdf),
        features=[
            oci.ai_document.models.DocumentFeature(feature_type="KEY_VALUE_EXTRACTION"),
            oci.ai_document.models.DocumentClassificationFeature(max_results=1)
        ]
    )

    res = client.analyze_document(req)

    data = {
        "VendorName": None,
        "VendorNameLogo": None,
        "InvoiceId": None,
        "InvoiceDate": None,
        "ShippingAddress": None,
        "BillingAddressRecipient": None,
        "AmountDue": None,
        "SubTotal": None,
        "ShippingCost": None,
        "InvoiceTotal": None,
        "Items": []
    }

    conf = {k: None for k in data if k != "Items"}

    for p in res.data.pages:
        for f in p.document_fields:
            name = f.field_label.name if f.field_label else None
            if name == "Items" or f.field_type == "LINE_ITEM_GROUP":
                data["Items"] = parse_items(f)
            elif name in data:
                val = text(f.field_value)
                data[name] = num(val) if name.endswith(("Total", "Due", "Cost")) else val
                conf[name] = f.field_label.confidence

    result = {
        "confidence": 1,
        "data": data,
        "dataConfidence": conf
    }

    os.makedirs("json_output", exist_ok=True)
    filename = f"json_output/result_{int(time.time())}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="127.0.0.1", port=8080)
