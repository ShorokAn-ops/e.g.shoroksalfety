import re
from fastapi import UploadFile


def is_pdf(upload: UploadFile, content: bytes) -> bool:
    return (
        (upload.content_type == "application/pdf"
         or (upload.filename and upload.filename.lower().endswith(".pdf")))
        and content.startswith(b"%PDF-")
    )


def clean_money(value: str): 
    if not value:
        return None
    v = re.sub(r"[^\d.]", "", value)
    return float(v) if v else None
