import unittest
import importlib
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from db_util import init_db, clean_db


class TestInvoiceExtraction(unittest.TestCase):

    def setUp(self):
        init_db()

        import app 
        importlib.reload(app)

        # Patch get_oci_client on the loaded module (survives reload correctly)
        self.patcher_get_client = patch.object(app, "get_oci_client")
        self.mock_get_client = self.patcher_get_client.start()

        # Fake OCI client returned by get_oci_client()
        self.mock_doc_client = MagicMock()
        self.mock_get_client.return_value = self.mock_doc_client

        # Helper for building OCI-like objects
        def obj(**kwargs):
            return type("obj", (), kwargs)()

        # Build analyze_document return value with .data.pages and .data.detected_document_types
        self.mock_doc_client.analyze_document.return_value = obj(
            data=obj(
                detected_document_types=[obj(document_type="INVOICE", confidence=1.0)],
                pages=[
                    obj(
                        document_fields=[
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="VendorName", confidence=0.95),
                                field_value=obj(value="SuperStore", text="SuperStore")),
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="InvoiceId", confidence=0.99),
                                field_value=obj(value="36259", text="36259")),
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="InvoiceDate", confidence=0.99),
                                field_value=obj(value="2012-03-06T00:00:00+00:00",
                                                text="2012-03-06T00:00:00+00:00")),
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="ShippingAddress", confidence=0.98),
                                field_value=obj(value="98103, Seattle, Washington, United States",
                                                text="98103, Seattle, Washington, United States")),
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="BillingAddressRecipient", confidence=0.99),
                                field_value=obj(value="Aaron Bergman", text="Aaron Bergman")),
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="SubTotal", confidence=0.90),
                                field_value=obj(value=53.82, text="53.82")),
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="ShippingCost", confidence=0.98),
                                field_value=obj(value=4.29, text="4.29")),
                            obj(field_type="KEY_VALUE",
                                field_label=obj(name="InvoiceTotal", confidence=0.99),
                                field_value=obj(value=58.11, text="58.11")),

                            obj(field_type="LINE_ITEM_GROUP",
                                field_label=obj(name="Items", confidence=None),
                                field_value=obj(
                                    items=[
                                        obj(field_value=obj(items=[
                                            obj(field_label=obj(name="Description"),
                                                field_value=obj(value="Newell 330 Art, Office Supplies, OFF-AR-5309",
                                                                text="Newell 330 Art, Office Supplies, OFF-AR-5309")),
                                            obj(field_label=obj(name="Name"),
                                                field_value=obj(value="Newell 330 Art, Office Supplies, OFF-AR-5309",
                                                                text="Newell 330 Art, Office Supplies, OFF-AR-5309")),
                                            obj(field_label=obj(name="Quantity"),
                                                field_value=obj(value=3, text="3")),
                                            obj(field_label=obj(name="UnitPrice"),
                                                field_value=obj(value=17.94, text="17.94")),
                                            obj(field_label=obj(name="Amount"),
                                                field_value=obj(value=53.82, text="53.82")),
                                        ]))
                                    ]
                                ))
                        ]
                    )
                ]
            )
        )

        self.client = TestClient(app.app)

    def tearDown(self):
        clean_db()
        self.patcher_get_client.stop()

    def test_extract_endpoint_fail_empty_file_400(self):
        response = self.client.post(
            "/extract",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_extract_endpoint_fail_not_pdf_400(self):
        response = self.client.post(
            "/extract",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_extract_endpoint_fail_oci_service_unavailable_503(self):
        self.mock_doc_client.analyze_document.side_effect = Exception("OCI down")

        with open("invoices_sample/invoice_Aaron_Bergman_36259.pdf", "rb") as f:
            response = self.client.post(
                "/extract",
                files={"file": ("invoice_Aaron_Bergman_36259.pdf", f, "application/pdf")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.json())

    def test_extract_endpoint_success(self):
        # Use real invoice file (your current flow)
        with open("invoices_sample/invoice_Aaron_Bergman_36259.pdf", "rb") as f:
            response = self.client.post(
                "/extract",
                files={"file": ("invoice_Aaron_Bergman_36259.pdf", f, "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertIn("data", result)
        data = result["data"]

        # Assert the stable core fields (no full dict equality)
        self.assertEqual(data.get("InvoiceId"), "36259")
        self.assertEqual(data.get("VendorName"), "SuperStore")
        self.assertEqual(data.get("BillingAddressRecipient"), "Aaron Bergman")

        # Date can be formatted differently – be flexible
        self.assertTrue((data.get("InvoiceDate")))

        # Floats: allow minor formatting differences
        self.assertAlmostEqual((data.get("SubTotal")), 53.82, places=2)
        self.assertAlmostEqual((data.get("ShippingCost")), 4.29, places=2)
        self.assertAlmostEqual((data.get("InvoiceTotal")), 58.11, places=2)

        # Items
        items = data.get("Items", [])
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 1)

        first = items[0]
        self.assertIn("Description", first)
        self.assertIn("Quantity", first)
        self.assertAlmostEqual((first.get("Amount")), 53.82, places=2)

    def test_extract_endpoint_fail_low_confidence(self):
        self.mock_doc_client.analyze_document.return_value.data.detected_document_types[0].confidence = 0.4

        with open("invoices_sample/invoice_Aaron_Bergman_36259.pdf", "rb") as f:
            response = self.client.post(
                "/extract",
                files={"file": ("invoice_Aaron_Bergman_36259.pdf", f, "application/pdf")},
            )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


if __name__ == "__main__":
    unittest.main()
