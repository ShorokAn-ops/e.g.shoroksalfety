import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base
import queries


def make_db(tmp_path):
    db_file = tmp_path / "integration.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def test_save_and_get_invoice(tmp_path):
    db = make_db(tmp_path)
    try:
        result = {
            "confidence": 0.95,
            "data": {
                "InvoiceId": "36259",
                "VendorName": "SuperStore",
                "InvoiceTotal": 58.11,
                "Items": [
                    {
                        "Description": "Newell 330 Art, Office Supplies, OFF-AR-5309",
                        "Name": "Newell 330 Art, Office Supplies, OFF-AR-5309",
                        "Quantity": 3.0,
                        "UnitPrice": 17.94,
                        "Amount": 53.82
                    }
            ]
            },
            "dataConfidence": {
                "VendorName": 0.9491271,
                "VendorNameLogo": 0.9491271,
                "InvoiceId": 0.9995704,
                "InvoiceDate": 0.9999474,
                "ShippingAddress": 0.9818857,
                "BillingAddressRecipient": 0.9970944,
                "AmountDue": 0.9994609,
                "SubTotal": 0.90709054,
                "ShippingCost": 0.98618066,
                "InvoiceTotal": 0.9974165
            }
        }
        

        queries.save_inv_extraction(db, result)

        inv = queries.get_invoice_by_id(db, "36259")
        assert inv is not None
        assert inv.InvoiceId == "36259"
        assert inv.VendorName == "SuperStore"
        assert inv.InvoiceTotal == 58.11
    finally:
        db.close()

def test_get_invoice_by_id_not_found(tmp_path):
    db = make_db(tmp_path)
    try:
        inv = queries.get_invoice_by_id(db, "12345")
        assert inv is None
    finally:
        db.close()


def test_get_by_vendor(tmp_path):
    db = make_db(tmp_path)
    try:
        queries.save_inv_extraction(
            db,
            {"confidence": 0.95, "data": {"InvoiceId": "35318", "VendorName": "SuperStore", 
                                            "Items": [{
                                                "Description": "Panasonic Kx-TS550 Phones, Technology, TEC-PH-5566",
                                                "Name": "Panasonic Kx-TS550 Phones, Technology, TEC-PH-5566",
                                                "Quantity": 3.0,
                                                "UnitPrice": 82.78,
                                                "Amount": 248.35
                                            }]}, 
                                            "dataConfidence": {
                                                "VendorName": 0.95504624,
                                                "VendorNameLogo": 0.95504624,
                                                "InvoiceId": 0.9996334,
                                                "InvoiceDate": 0.99989593,
                                                "ShippingAddress": 0.9998233,
                                                "BillingAddressRecipient": None,
                                                "AmountDue": 0.69264007,
                                                "SubTotal": None,
                                                "ShippingCost": 0.9879584,
                                                "InvoiceTotal": 0.97781485
                                            }
                                        },
        )
        queries.save_inv_extraction(
            db,
            {"confidence": 0.95, "data": {"InvoiceId": "36259", "VendorName": "SuperStore", 
                                          "Items":  [
                                            {
                                                "Description": "Newell 330 Art, Office Supplies, OFF-AR-5309",
                                                "Name": "Newell 330 Art, Office Supplies, OFF-AR-5309",
                                                "Quantity": 3.0,
                                                "UnitPrice": 17.94,
                                                "Amount": 53.82
                                            }
                                        ]
                                        }, "dataConfidence":  {
                                                "VendorName": 0.9491271,
                                                "VendorNameLogo": 0.9491271,
                                                "InvoiceId": 0.9995704,
                                                "InvoiceDate": 0.9999474,
                                                "ShippingAddress": 0.9818857,
                                                "BillingAddressRecipient": 0.9970944,
                                                "AmountDue": 0.9994609,
                                                "SubTotal": 0.90709054,
                                                "ShippingCost": 0.98618066,
                                                "InvoiceTotal": 0.9974165
                                            }
                                        },
        )
    

        superstore = queries.get_invoices_by_vendor(db, "SuperStore")
        assert len(superstore) == 2
    finally:
        db.close()

def test_get_invoices_by_vendor_not_found(tmp_path):
    db = make_db(tmp_path)
    try:
        invoices = queries.get_invoices_by_vendor(db, "shorok")
        assert invoices == []
    finally:
        db.close()
