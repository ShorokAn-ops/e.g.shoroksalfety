from fastapi import FastAPI, UploadFile, File
import oci
import base64
from db_util import init_db, save_inv_extraction
"""
echo "[" > ~/Desktop/notes.json
first=1
for f in invoices_sample/*.pdf; do
  if [ $first -eq 0 ]; then
    echo "," >> ~/Desktop/notes.json
  fi
  first=0
  curl -s -X POST "http://127.0.0.1:8080/extract" -F "file=@$f" >> ~/Desktop/notes.json
done
echo "]" >> ~/Desktop/notes.json
"""

app = FastAPI()

# Load OCI config from ~/.oci/config
config = oci.config.from_file()

doc_client = oci.ai_document.AIServiceDocumentClient(config)



"""
@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    pdf_bytes = await file.read()

    # Base64 encode PDF
    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    document = oci.ai_document.models.InlineDocumentDetails(
        data=encoded_pdf
    )
    
    request = oci.ai_document.models.AnalyzeDocumentDetails(
        document=document,
        features=[
            oci.ai_document.models.DocumentFeature(
                feature_type="KEY_VALUE_EXTRACTION"
            ),
            oci.ai_document.models.DocumentClassificationFeature(
                max_results=5
            )
        ]
    )

    response = doc_client.analyze_document(request)
    data = {}
    data_confidence = {}

    for page in response.data.pages:
        if page.document_fields:
            for field in page.document_fields:
                field_name = field.field_label.name
                field_confidence = field.field_label.confidence if field.field_label else None
                field_value = field.field_value.text
                field_item = field.field_value.items if field.field_value else None
                if field.field_type == "LINE_ITEM_GROUP" or field_name == "Items":
                    if "Items" not in data:
                        data["Items"] = parse_line_items(field)

                else:
                    if field_name:
                        data[field_name] = field_value
                        data_confidence[field_name] = field_confidence

                data[field_name] = field_value
                data_confidence[field_name] = field_confidence
                data[field_name] = field_item
    #if page.document_fields and page.document_fields[0].field_label and page.document_fields[0].field_value.items:

        #ield_item = page.document_fields[0].field_value.items[0]
        data[field_name] = field_value
        data[field_name] = field_item
        data_confidence[field_name] = field_confidence
    
    result = {
        "confidence": field_confidence,
        "data": data ,
        "dataConfidence": data_confidence
    }
"""

    # TODO: call to save_inv_extraction(result)    ( no need to change this function)

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    pdf_bytes = await file.read()

    # Base64 encode PDF
    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    document = oci.ai_document.models.InlineDocumentDetails(
        data=encoded_pdf
    )
    
    request = oci.ai_document.models.AnalyzeDocumentDetails(
        document=document,
        features=[
            oci.ai_document.models.DocumentFeature(
                feature_type="KEY_VALUE_EXTRACTION"
            ),
            oci.ai_document.models.DocumentClassificationFeature(
                max_results=5
            )
        ]
    )
 #הפונקציה מנסה לחלץ ערך משדה של OCI Document AI בצורה בטוחה, קודם מטקסט רגיל ואם אין – מערך מנורמל, אחרת מחזירה None.   
    def get_text_from_field_value(v):
        if v is None:
            return None

        #ניסיון לקחת טקסט רגיל
        t = getattr(v, "text", None)
        if t not in (None, ""):
            return t

        #ניסיון לקחת ערך מנורמל
        nv = getattr(v, "normalized_value", None)
        if nv not in (None, ""):
            return nv
        return None


    def parse_line_items(items_group_field):
        out = []
        # שליפת הערך של קבוצת הפריטים
        group_value = items_group_field.field_value
        if group_value is None:
            return out
        #שליפת כל שורות החשבונית
        rows = getattr(group_value, "items", None)  
        if not rows:
            return out
        #כל row = שורה אחת בחשבונית
        for row in rows:
            #שליפת עמודות של השורה
            #cols = (Description, Quantity, Price וכו
            row_value = getattr(row, "field_value", None)
            cols = getattr(row_value, "items", None) if row_value else None 
            if not cols:
                continue

            col_map = {}
            #כדי שאפשר יהיה לשלוף שדות בקלות לפי שם.
            for c in cols:
                label = None
                if getattr(c, "field_label", None) and getattr(c.field_label, "name", None):
                    label = c.field_label.name
                elif getattr(c, "field_name", None):
                    label = c.field_name
                col_map[label] = c

            #מקבלת כמה שמות אפשריים לאותו שדה
            #(כי OCI לא תמיד מחזיר אותו שם).
            #מחפשת את הראשון שקיים מחזירה את הערך שלו אם אין NONE או מחרוזת ריקה
 
            def col(*names):
                for n in names:
                    f = col_map.get(n)
                    if f and getattr(f, "field_value", None):
                        val = get_text_from_field_value(f.field_value)
                        if val not in (None, ""):
                            return val
                return None
            
            #יצירת Item  (מילון(בפורמט הנדרש
            out.append({
                "Description": col("Description", "ItemDescription", "Desc"),
                "Name": col("Name", "Item", "ProductName"),
                "Quantity": col("Quantity", "Qty"),
                "UnitPrice": col("UnitPrice", "Price", "UnitCost"),
                "Amount": col("Amount", "LineTotal", "Total"),
            })

        return out

    response = doc_client.analyze_document(request)
    data = {}
    data_confidence = {}

    for page in response.data.pages:
        if page.document_fields:
            for field in page.document_fields:
                field_name = field.field_label.name if field.field_label else None
                field_confidence = field.field_label.confidence if field.field_label else None
                field_value = get_text_from_field_value(field.field_value)
                if field.field_type == "LINE_ITEM_GROUP" or field_name == "Items":
                    if "Items" not in data:
                        data["Items"] = parse_line_items(field)

                else:
                    if field_name:
                        data[field_name] = field_value
                        data_confidence[field_name] = field_confidence



    result = {
        "confidence": 1,
        "data": data,
        "dataConfidence": data_confidence
    }
    
    return result    


if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8080)