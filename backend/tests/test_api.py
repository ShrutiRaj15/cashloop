import os
import sys
import pytest
from fastapi.testclient import TestClient

os.environ["CASHLOOP_DB_PATH"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cashloop.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app

client = TestClient(app)

def test_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["app"] == "CashLoop API"

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

def test_get_businesses():
    res = client.get("/api/businesses")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 30
    assert data[0]["id"] == "biz_001"

def test_get_single_business():
    res = client.get("/api/businesses/biz_001")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Sharma Provision & Kirana Store"
    assert data["category"] == "kirana"

def test_get_forecast():
    res = client.get("/api/forecasts/biz_001?horizon=30")
    assert res.status_code == 200
    data = res.json()
    assert data["horizon_days"] == 30
    assert len(data["daily_forecasts"]) == 30
    assert "recommendations" in data

def test_get_explanation():
    res = client.get("/api/explanations/biz_001")
    assert res.status_code == 200
    data = res.json()
    assert "explanation" in data
    assert "Sharma Provision" in data["explanation"]
    assert "guardrail_verification" in data

def test_get_invoices_and_extract():
    res_inv = client.get("/api/invoices/biz_001")
    assert res_inv.status_code == 200
    assert len(res_inv.json()) > 0

    # Test extract
    extract_payload = {
        "raw_text": "Invoice from Agarwal Traders, GSTIN: 23AABBA1234F1Z1, Bill No: INV-9901, Amount: Rs. 42,000"
    }
    res_extract = client.post("/api/invoices/extract", json=extract_payload)
    assert res_extract.status_code == 200
    ext = res_extract.json()
    assert ext["invoice_number"] == "INV-9901"
    assert ext["amount"] == 42000.0

def test_closed_loop_and_action():
    res = client.get("/api/closed-loop/biz_001")
    assert res.status_code == 200
    data = res.json()
    assert "overall_wape" in data
    assert "actions" in data

def test_lender_portfolio():
    res = client.get("/api/lender/portfolio")
    assert res.status_code == 200
    data = res.json()
    assert "portfolio_summary" in data
    assert data["portfolio_summary"]["total_msmes"] >= 30
    assert len(data["businesses"]) >= 30

def test_statement_upload_csv():
    # 1. Valid CSV
    valid_csv = "date,type,amount,description\n2026-11-01,inflow,50000,UPI Store Sales\n2026-11-02,outflow,12000,Inventory Restock"
    files = {"file": ("statement.csv", valid_csv, "text/csv")}
    data = {"business_id": "biz_001"}
    res = client.post("/api/statements/upload", data=data, files=files)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["transactions_imported"] == 2

    # 2. Empty CSV error handling
    empty_files = {"file": ("empty.csv", "", "text/csv")}
    res_empty = client.post("/api/statements/upload", data=data, files=empty_files)
    assert res_empty.status_code == 400

    # 3. Malformed invalid file format
    txt_files = {"file": ("statement.pdf", "dummy", "application/pdf")}
    res_malformed = client.post("/api/statements/upload", data=data, files=txt_files)
    assert res_malformed.status_code == 400

def test_invoice_verification_queue_api():
    # Upload an invoice text
    payload = {
        "business_id": "biz_001",
        "raw_text": "Bill from Jai Hind Traders, Bill No: INV-JAI-992, Date: 2026-10-10, Due: 2026-11-15, Total: Rs. 28,000"
    }
    res = client.post("/api/invoices/upload", json=payload)
    assert res.status_code == 200
    verif_id = res.json()["verification_id"]

    # Check review queue
    res_q = client.get("/api/invoices/review-queue/all")
    assert res_q.status_code == 200

    # Submit decision
    res_dec = client.post(f"/api/invoices/review-queue/{verif_id}/decide", json={"decision": "approve", "notes": "Approved"})
    assert res_dec.status_code == 200
    assert res_dec.json()["new_status"] == "approved_by_human"

def test_lender_interventions_api():
    payload = {
        "business_id": "biz_001",
        "intervention_type": "reminder_sent",
        "predicted_shortfall": 35000.0,
        "notes": "Sent SMS reminder on payment schedule"
    }
    res = client.post("/api/lender/interventions", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    # Get history
    res_hist = client.get("/api/lender/interventions")
    assert res_hist.status_code == 200
    assert len(res_hist.json()) > 0
