import os
import sys
import pytest
from datetime import date, timedelta

os.environ["CASHLOOP_DB_PATH"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cashloop.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models.database import SessionLocal, Base, engine
from app.models.schema import Business, Customer, Invoice, Transaction, PredictionLog, ActionRecommendation
from app.services.loops.forecast_accuracy_loop import ForecastAccuracyLoop
from app.services.loops.customer_behavior_loop import CustomerBehaviorLoop
from app.services.loops.action_outcome_loop import ActionOutcomeLoop
from app.services.loops.document_verification_loop import DocumentVerificationLoop
from app.services.loops.lender_early_warning_loop import LenderEarlyWarningLoop

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

def test_forecast_accuracy_loop(db):
    loop = ForecastAccuracyLoop(db)
    biz_id = "biz_001"

    # Insert a test pending prediction for yesterday
    yesterday = date(2026, 10, 30)
    today = date(2026, 10, 31)

    pred = PredictionLog(
        id="pred_test_acc_01",
        business_id=biz_id,
        prediction_date=date(2026, 10, 1),
        target_date=yesterday,
        horizon_days=29,
        predicted_p10=200000.0,
        predicted_p50=250000.0,
        predicted_p90=300000.0,
        predicted_naive=240000.0,
        status="pending"
    )
    db.add(pred)
    db.commit()

    res = loop.evaluate_daily_accuracy(biz_id, today)
    assert res["target_date"] == yesterday.isoformat()
    assert "absolute_error" in res
    assert "trust_score" in res
    assert 0 <= res["trust_score"] <= 100

def test_customer_behavior_loop_sharpening(db):
    loop = CustomerBehaviorLoop(db)
    cust = db.query(Customer).filter(Customer.business_id == "biz_001").first()
    assert cust is not None

    inv = db.query(Invoice).filter(Invoice.customer_id == cust.id).first()
    assert inv is not None

    initial_std = cust.delay_std_days
    initial_obs = cust.observations_count or 1

    # Simulate payment arrival 15 days after due date
    payment_date = inv.due_date + timedelta(days=15)
    update_res = loop.record_payment_arrival(cust.id, inv.id, payment_date)

    assert update_res["actual_delay_days"] == 15
    assert update_res["observations_count"] == initial_obs + 1
    # Check that uncertainty narrowed (std sharpened)
    assert update_res["new_std_delay"] <= initial_std

    # Check sharpening summary
    summary = loop.get_sharpening_summary("biz_001")
    assert len(summary) > 0
    assert "sharpening_gain_pct" in summary[0]

def test_action_outcome_bandit_loop(db):
    loop = ActionOutcomeLoop(db)

    # Check bandit weights
    weights = loop.get_bandit_weights("kirana")
    assert "early_payment_discount" in weights
    assert "delay_supplier_invoice" in weights
    assert "ucb_score" in weights["early_payment_discount"]

    # Rank recommendations
    sample_recs = [
        {"action_type": "delay_supplier_invoice", "title": "Delay supplier"},
        {"action_type": "early_payment_discount", "title": "Early discount"},
    ]
    ranked = loop.rank_and_score_recommendations(sample_recs, "kirana")
    assert len(ranked) == 2
    assert "bandit_score" in ranked[0]
    assert ranked[0]["bandit_score"] >= ranked[1]["bandit_score"]

def test_document_verification_loop_with_retries(db):
    loop = DocumentVerificationLoop(db)
    biz_id = "biz_001"

    # Test 1: Future receivable invoice (should verify)
    valid_text = """
    Invoice from Om Wholesale Mart
    GSTIN: 23AABBO1234F1Z1
    Bill No: INV-VALID-101
    Date: 2026-10-05
    Due Date: 2026-11-20
    Total Amount: Rs. 35,000.00
    """
    res = loop.process_and_verify_invoice(biz_id, valid_text)
    assert res["validation_status"] in ["verified", "flagged_for_human_review"]
    assert "retry_count" in res

    # Test 2: Review queue and human decision
    queue = loop.get_review_queue(biz_id)
    if queue:
        item = queue[0]
        decision_res = loop.human_decision(item["id"], "approve", "Verified with physical bill")
        assert decision_res["status"] == "success"
        assert decision_res["new_status"] == "approved_by_human"

def test_lender_early_warning_loop(db):
    loop = LenderEarlyWarningLoop(db)
    
    # Scan risks
    risks = loop.scan_portfolio_risks()
    assert len(risks) > 0

    # Record intervention for first flagged borrower
    flagged = risks[0]
    res = loop.record_intervention(
        business_id=flagged["business_id"],
        intervention_type="credit_line_offered",
        predicted_shortfall=flagged["projected_shortfall"],
        notes="Offered 30-day working capital credit line to bridge cash crunch."
    )
    assert res["status"] == "active"
    assert res["intervention_type"] == "credit_line_offered"

    # Evaluate outcomes
    outcomes = loop.evaluate_intervention_outcomes(date.today())
    assert "avoided" in outcomes
