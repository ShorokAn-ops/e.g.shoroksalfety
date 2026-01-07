# API Traceability Matrix

| API Endpoint                       | Test File                            | Test Case(s)                                                                                                                                                                              |
| ---------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| POST /extract                      | test/test_extract.py                 | `test_extract_success_invoice_confidence_high` (200), `fail_empty_file` (400) `test_extract_endpoint_fail_not_pdf` (400) `fail_confidence_low` (400) `fail_oci_service_unavailable` (503) |
| GET /invoice/{invoice_id}          | test/test_invoice_by_id.py           | `test_get_invoice_by_id_success_200` (200), `test_get_invoice_by_id_not_found` (404)                                                                                                      |
| GET /invoices/vendor/{vendor_name} | test/test_invoices_by_vendor_name.py | `test_get_invoices_by_vendor_success` (200), `test_get_invoices_by_vendor_not_found_unknown` (200 + empty results)                                                                        |
