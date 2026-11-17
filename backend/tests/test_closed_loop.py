import os
import sys
import pytest
from datetime import date, timedelta

os.environ["CASHLOOP_DB_PATH"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cashloop.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.llm import MockLLMProvider, get_llm_service
from app.services.recommendations import RecommendationEngine
from app.services.closed_loop import ClosedLoopService
from app.services.simulation import TimeMachineSimulation
from app.models.database import SessionLocal
from app.models.schema import Business, PredictionLog, ActionRecommendation

def test_mock_llm_explanation():
    llm = MockLLMProvider()
    biz = {"name": "Sharma Kirana Store", "category": "kirana"}
    forecast = {
        "danger_days_count": 5,
        "first_danger_date": "2026-11-20",
        "max_shortfall": 45000.0,
        "min_cash_threshold": 25000.0,
        "min_projected_balance_p50": -20000.0,
        "primary_driver": "GST 3B tax payment on 20th"
    }

    # English explanation
    exp_en = llm.explain_cash_flow(biz, forecast, "en")
    assert "Sharma Kirana Store" in exp_en
    assert "45,000" in exp_en
    assert "VAT" in exp_en or "GST" in exp_en or "tax" in exp_en.lower()

def test_invoice_extraction():
    llm = MockLLMProvider()
    raw_invoice = """
    Vardhman Textile Wholesalers Pvt Ltd
    Ring Road Market, Surat, Gujarat
    GSTIN: 24AAACV1234F1Z8
    Invoice No: INV-2026-8891
    Date: 2026-11-05
    Due Date: 2026-12-05
    Item: Pure Silk Sarees - 100 pcs
    Total Amount: INR 1,45,000.00
    Payment Terms: Net 30
    """
    extracted = llm.extract_invoice(raw_invoice)
    assert extracted["invoice_number"] == "INV-2026-8891"
    assert extracted["amount"] == 145000.0
    assert extracted["gstin"] == "24AAACV1234F1Z8"
    assert "Vardhman Textile" in extracted["vendor_name"]

def test_costed_recommendations_generation():
    engine = RecommendationEngine()
    biz = {"id": "biz_001", "name": "Sharma Kirana Store", "category": "kirana"}
    forecast = {
        "danger_days": [{"date": "2026-11-20", "shortfall": 35000.0}],
        "max_shortfall": 35000.0
    }
    open_invoices = [
        {"id": "inv_1", "customer_id": "c1", "invoice_number": "INV-001", "amount": 60000.0}
    ]
    customers_map = {"c1": {"name": "Goyal Traders"}}

    recs = engine.generate_recommendations(biz, forecast, open_invoices, customers_map, date(2026, 11, 1))
    assert len(recs) >= 3

    # Check early payment discount
    disc_rec = [r for r in recs if r["action_type"] == "early_payment_discount"][0]
    assert disc_rec["estimated_cost"] > 0
    assert disc_rec["cash_unlocked"] > disc_rec["estimated_cost"]
    assert disc_rec["net_benefit"] > 0
    assert "Goyal Traders" in disc_rec["title"]
    assert "description" in disc_rec

def test_closed_loop_service_evaluation():
    db = SessionLocal()
    try:
        service = ClosedLoopService(db)
        biz_id = "biz_001"

        # Log mock predictions
        mock_forecasts = [
            {"date": "2026-05-01", "balance_p10": 200000.0, "balance_p50": 250000.0, "balance_p90": 300000.0, "naive_balance": 240000.0},
            {"date": "2026-05-02", "balance_p10": 205000.0, "balance_p50": 255000.0, "balance_p90": 305000.0, "naive_balance": 245000.0},
        ]
        service.log_predictions(biz_id, date(2026, 4, 30), mock_forecasts)

        # Evaluate against actuals
        eval_result = service.evaluate_realized_predictions(biz_id, date(2026, 5, 5))
        assert eval_result["evaluated_count"] >= 2
        assert "avg_ape" in eval_result
        assert "interval_coverage" in eval_result

        # Check drift detection
        drift_res = service.check_and_record_drift(biz_id, date(2026, 5, 5), window_days=14, threshold_wape=0.90)
        assert "drift_detected" in drift_res
    finally:
        db.close()

def test_simulation_runner_short():
    # Run a fast 3-week simulation slice on 2 businesses
    sim = TimeMachineSimulation(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 22),
        step_days=7,
        businesses_to_simulate=["biz_001", "biz_003"] # includes crunch biz_003
    )
    summary = sim.run()
    assert len(summary["weekly_metrics"]) > 0
    assert "actions_summary" in summary
    assert "crunch_detection" in summary
    assert os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "simulation_report.md"))
    assert os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "simulation_metrics.json"))
