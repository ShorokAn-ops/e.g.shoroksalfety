import unittest
from fastapi.testclient import TestClient

from app import app
from db_util import init_db, clean_db
from db import get_db


class TestInvoicesByVendorName(unittest.TestCase):

    def setUp(self):
        init_db()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        clean_db()

    def test_get_invoices_by_vendor_success(self):
        vendor = "SuperStore"

        with get_db() as conn:
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO invoices (
                    InvoiceId, VendorName, InvoiceDate,
                    BillingAddressRecipient, ShippingAddress,
                    SubTotal, ShippingCost, InvoiceTotal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "INV-101", vendor, "2012-03-06",
                "Aaron Bergman", "Seattle",
                10.0, 1.0, 11.0
            ))

            cur.execute("""
                INSERT INTO invoices (
                    InvoiceId, VendorName, InvoiceDate,
                    BillingAddressRecipient, ShippingAddress,
                    SubTotal, ShippingCost, InvoiceTotal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "INV-102", vendor, "2012-03-07",
                "Aaron Bergman", "Seattle",
                20.0, 2.0, 22.0
            ))

            conn.commit()

        # Act
        response = self.client.get(f"/invoices/vendor/{vendor}")

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["VendorName"], vendor)
        self.assertEqual(body["TotalInvoices"], 2)
        self.assertIn("invoices", body)
        self.assertEqual(len(body["invoices"]), 2)

        returned_ids = {inv["InvoiceId"] for inv in body["invoices"]}
        self.assertSetEqual(returned_ids, {"INV-101", "INV-102"})

    def test_get_invoices_by_vendor_not_found_unknown(self):
        response = self.client.get("/invoices/vendor/shorok")

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["VendorName"], "Unknown Vendor")
        self.assertEqual(body["TotalInvoices"], 0)
        self.assertEqual(body["invoices"], [])


if __name__ == "__main__":
    unittest.main()

