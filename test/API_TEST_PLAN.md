# API Test Plan

## What to test

- **POST /extract**: success (valid invoice, confidence ≥ 0.9) and failure (low confidence / invalid invoice).
- **GET /invoice/{invoice_id}**: success (exists) and failure (not found).
- **GET /invoices/vendor/{vendor_name}**: success (invoices exist) and no-data case (empty list returned).

## Test strategy

Integration tests using FastAPI TestClient, real SQLite DB, and mocked external OCI service.
Tests are written with `unittest` and executed using `pytest`.

## Environment

Local execution and GitHub Actions CI.

## Success & reporting

All API endpoints are covered.  
Code coverage is measured with `pytest-cov` and reported in terminal and HTML.
