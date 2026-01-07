import unittest
from fastapi.testclient import TestClient

from app import app
from db_util import init_db, clean_db, get_db


class TestInvoiceById(unittest.TestCase):

    def setUp(self):
        init_db()
        self.client = TestClient(app)

    def tearDown(self):
        clean_db()

    def test_get_invoice_by_id_success_200(self):
        invoice_id = "36259"

        with get_db() as conn:
            cur = conn.cursor()

            cur.execute("""
                INSERT OR REPLACE INTO invoices (
                    InvoiceId, VendorName, InvoiceDate, BillingAddressRecipient,
                    ShippingAddress, SubTotal, ShippingCost, InvoiceTotal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_id,
                "SuperStore",
                "2012-03-06T00:00:00+00:00",
                "Aaron Bergman",
                "98103, Seattle, Washington, United States",
                53.82,
                4.29,
                58.11
            ))

            cur.execute("""
                INSERT INTO items (InvoiceId, Description, Name, Quantity, UnitPrice, Amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                invoice_id,
                "Newell 330 Art, Office Supplies, OFF-AR-5309",
                "Newell 330 Art, Office Supplies, OFF-AR-5309",
                3,
                17.94,
                53.82
            ))

            conn.commit()

        # Act
        response = self.client.get(f"/invoice/{invoice_id}")

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["InvoiceId"], invoice_id)
        self.assertEqual(body["VendorName"], "SuperStore")
        self.assertIn("Items", body)
        self.assertEqual(len(body["Items"]), 1)
        self.assertEqual(body["Items"][0]["Quantity"], 3)

    def test_get_invoice_by_id_not_found(self):
        # Act
        response = self.client.get("/invoice/12345")

        # Assert
        self.assertEqual(response.status_code, 404)
        body = response.json()

        # אצלך ה-handler מחזיר {"error": "..."}
        self.assertIn("error", body)
        self.assertEqual(body["error"], "Invoice not found")

if __name__ == "__main__":
    unittest.main()
