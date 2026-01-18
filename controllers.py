from sqlalchemy.orm import Session
import queries
from models import Invoice


def save_extraction(
    db: Session,
    data: dict,
    data_confidence: dict,
    doc_confidence: float,
) -> Invoice:
    """
    Save invoice extraction result into the database.
    """

    result = {
        "confidence": doc_confidence,
        "data": data,
        "dataConfidence": data_confidence,
    }

    queries.save_inv_extraction(db, result)

    # Return the saved invoice (useful for tests / callers)
    invoice_id = data.get("InvoiceId")
    if not invoice_id:
        return None

    return queries.get_invoice_by_id(db, invoice_id)


def get_invoice(db: Session, invoice_id: str) -> Invoice | None:
    """
    Get a single invoice by ID.
    """
    return queries.get_invoice_by_id(db, invoice_id)


def get_by_vendor(db: Session, vendor_name: str) -> list[Invoice]:
    """
    Get all invoices for a specific vendor.
    """
    return queries.get_invoices_by_vendor(db, vendor_name)
