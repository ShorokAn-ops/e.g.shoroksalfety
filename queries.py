from sqlalchemy.orm import Session, joinedload

from models import Invoice, Confidence, Item


def save_inv_extraction(db: Session, result: dict) -> None:
    data = (result.get("data") or {})
    conf = (result.get("dataConfidence") or {})

    invoice_id = data.get("InvoiceId")
    if not invoice_id:
        return

    invoice = db.query(Invoice).filter_by(InvoiceId=invoice_id).first()
    if not invoice:
        invoice = Invoice(InvoiceId=invoice_id)
        db.add(invoice)

    # update invoice fields
    invoice.VendorName = data.get("VendorName")
    invoice.InvoiceDate = data.get("InvoiceDate")
    invoice.BillingAddressRecipient = data.get("BillingAddressRecipient")
    invoice.ShippingAddress = data.get("ShippingAddress")
    invoice.SubTotal = data.get("SubTotal")
    invoice.ShippingCost = data.get("ShippingCost")
    invoice.InvoiceTotal = data.get("InvoiceTotal")

    # upsert confidence (one-to-one)
    if invoice.confidences is None:
        invoice.confidences = Confidence(InvoiceId=invoice_id)

    invoice.confidences.VendorName = conf.get("VendorName")
    invoice.confidences.InvoiceDate = conf.get("InvoiceDate")
    invoice.confidences.BillingAddressRecipient = conf.get("BillingAddressRecipient")
    invoice.confidences.ShippingAddress = conf.get("ShippingAddress")
    invoice.confidences.SubTotal = conf.get("SubTotal")
    invoice.confidences.ShippingCost = conf.get("ShippingCost")
    invoice.confidences.InvoiceTotal = conf.get("InvoiceTotal")

    # replace items (simple + deterministic)
    invoice.items.clear()
    for it in (data.get("Items") or []):
        invoice.items.append(Item(
            InvoiceId=invoice_id,
            Description=it.get("Description"),
            Name=it.get("Name"),
            Quantity=it.get("Quantity"),
            UnitPrice=it.get("UnitPrice"),
            Amount=it.get("Amount"),
        ))

    db.commit()


def get_invoice_by_id(db: Session, invoice_id: str):
    return (
        db.query(Invoice)
        .options(joinedload(Invoice.items))
        .filter_by(InvoiceId=invoice_id)
        .first()
    )


def get_invoices_by_vendor(db: Session, vendor_name: str):
    invoices = (
        db.query(Invoice)
        .filter(Invoice.VendorName == vendor_name)
        .order_by(Invoice.InvoiceDate.asc())
        .all()
    )

    result = []
    for inv in invoices:
        inv_full = get_invoice_by_id(db, inv.InvoiceId)
        if inv_full:
            result.append(inv_full)
    return result


def clean_db(db: Session) -> None:
    db.query(Item).delete()
    db.query(Confidence).delete()
    db.query(Invoice).delete()
    db.commit()
