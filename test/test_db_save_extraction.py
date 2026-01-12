import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base
import queries

"""
Integration tests for DB functionality only.
These tests use a real SQLite database and do not involve FastAPI or HTTP.
"""


@pytest.fixture()
def db_session(tmp_path):
    db_file = tmp_path / "integration.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_save_and_get_invoice(db_session):
    result = {
        "confidence": 0.95,
        "data": {
            "InvoiceId": "A1",
            "VendorName": "ACME",
            "InvoiceTotal": 10.0,
            "Items": [],
        },
        "dataConfidence": {},
    }


    # save
    queries.save_inv_extraction(db_session, result)

    # get
    inv = queries.get_invoice_by_id(db_session, "A1")
    assert inv is not None
    assert inv.InvoiceId == "A1"
    assert inv.VendorName == "ACME"
    assert inv.InvoiceTotal == 10.0


def test_get_by_vendor(db_session):
    queries.save_inv_extraction(
        db_session,
        {
            "confidence": 0.95,
            "data": {"InvoiceId": "A1", "VendorName": "ACME", "Items": []},
            "dataConfidence": {},
        },
    )
    queries.save_inv_extraction(
        db_session,
        {
            "confidence": 0.95,
            "data": {"InvoiceId": "A2", "VendorName": "ACME", "Items": []},
            "dataConfidence": {},
        },
    )
    queries.save_inv_extraction(
        db_session,
        {
            "confidence": 0.95,
            "data": {"InvoiceId": "B1", "VendorName": "OTHER", "Items": []},
            "dataConfidence": {},
        },
    )

    acme = queries.get_invoices_by_vendor(db_session, "ACME")
    assert len(acme) == 2
