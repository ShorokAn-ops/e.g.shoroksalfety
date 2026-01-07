# API Traceability Matrix

| API Endpoint                       | Test File                            | Test Case(s)                                                                                                               |
| ---------------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| POST /extract                      | test/test_extract.py                 | `test_extract_success_invoice_confidence_high` (200), `test_extract_endpoint_fail_empty_file_returns_400` (400) `test_extract_endpoint_fail_not_pdf_returns_400` (400)  `test_extract_fail_confidence_low` (400)  `test_extract_endpoint_fail_oci_service_unavailable_returns_503` (503)                             |
| GET /invoice/{invoice_id}          | test/test_invoice_by_id.py           | `test_get_invoice_by_id_success_200` (200), `test_get_invoice_by_id_not_found_404` (404)                                   |
| GET /invoices/vendor/{vendor_name} | test/test_invoices_by_vendor_name.py | `test_get_invoices_by_vendor_success` (200), `test_get_invoices_by_vendor_not_found_returns_unknown` (200 + empty results) |
