import os
import sys
import pytest
from datetime import date, timedelta
import numpy as np

os.environ["CASHLOOP_DB_PATH"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cashloop.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.ml.features import get_festival_features, build_calendar_features_df, build_daily_timeseries_df
from app.ml.invoice_delay import InvoiceDelayModel
from app.ml.forecaster import CashFlowForecaster
from app.ml.backtest import run_backtest, calculate_wape, calculate_mape
from app.models.database import SessionLocal
from app.models.schema import Business, Transaction, RecurringPayment, Invoice, Customer

def test_feature_engineering_festivals():
    # Diwali 2026 is Nov 8, 2026. Nov 7 should be active with high multiplier
    feats_diwali = get_festival_features(date(2026, 11, 7), "sweet_shop")
    assert feats_diwali["is_festival_active"] == 1.0
    assert feats_diwali["festival_multiplier"] > 2.0

    # Normal day in July
    feats_normal = get_festival_features(date(2026, 7, 10), "sweet_shop")
    assert feats_normal["is_festival_active"] == 0.0
    assert feats_normal["festival_multiplier"] == 1.0

def test_calendar_features_df():
    dates = [date(2026, 11, 1) + timedelta(days=i) for i in range(14)]
    df = build_calendar_features_df(dates, "kirana")
    assert len(df) == 14
    assert "is_salary_week" in df.columns
    assert "is_gst_cycle" in df.columns
    assert "sin_day_of_week" in df.columns
    # Check salary week flag for Nov 1 to Nov 7
    assert df.loc[0, "is_salary_week"] == 1.0
    assert df.loc[10, "is_salary_week"] == 0.0

def test_invoice_delay_model_quantiles():
    model = InvoiceDelayModel()
    customers = [
        {"id": "c1", "name": "Buyer 1", "payment_habit": "disciplined", "avg_delay_days": 1.0, "delay_std_days": 1.5},
        {"id": "c2", "name": "Buyer 2", "payment_habit": "chronic_late", "avg_delay_days": 22.0, "delay_std_days": 3.0},
    ]
    # Synthetic paid invoices
    hist_invoices = []
    for i in range(30):
        c_id = "c1" if i % 2 == 0 else "c2"
        delay = 1 if c_id == "c1" else 22
        hist_invoices.append({
            "id": f"inv_{i}",
            "customer_id": c_id,
            "invoice_number": f"INV-{i}",
            "amount": 15000.0,
            "issue_date": date(2026, 1, 1),
            "due_date": date(2026, 1, 31),
            "paid_date": date(2026, 1, 31) + timedelta(days=delay),
            "actual_delay_days": delay
        })

    model.fit(hist_invoices, customers)
    assert model.is_fitted

    open_invs = [
        {"id": "open_1", "customer_id": "c1", "invoice_number": "INV-O1", "amount": 20000.0, "issue_date": date(2026, 10, 1), "due_date": date(2026, 10, 31)},
        {"id": "open_2", "customer_id": "c2", "invoice_number": "INV-O2", "amount": 50000.0, "issue_date": date(2026, 10, 1), "due_date": date(2026, 10, 31)},
    ]
    preds = model.predict_delays(open_invs, customers)
    assert len(preds) == 2
    for p in preds:
        assert p["delay_p10"] <= p["delay_p50"] <= p["delay_p90"]

    # Chronic late buyer should have higher predicted delay than disciplined buyer
    c1_pred = [p for p in preds if p["invoice_id"] == "open_1"][0]
    c2_pred = [p for p in preds if p["invoice_id"] == "open_2"][0]
    assert c2_pred["delay_p50"] > c1_pred["delay_p50"]

def test_forecaster_30_day_horizon_and_monotonicity():
    db = SessionLocal()
    try:
        biz = db.query(Business).filter(Business.id == "biz_001").first()
        txs = db.query(Transaction).filter(Transaction.business_id == "biz_001").all()
        recs = db.query(RecurringPayment).filter(RecurringPayment.business_id == "biz_001").all()
        invs = db.query(Invoice).filter(Invoice.business_id == "biz_001").all()
        custs = db.query(Customer).filter(Customer.business_id == "biz_001").all()

        biz_dict = {"id": biz.id, "category": biz.category, "min_cash_threshold": biz.min_cash_threshold, "initial_balance": biz.initial_balance}
        tx_dicts = [{"id": t.id, "date": t.date, "type": t.type, "category": t.category, "amount": t.amount, "is_banked": t.is_banked, "balance_after": t.balance_after} for t in txs]
        rec_dicts = [{"id": r.id, "title": r.title, "category": r.category, "amount": r.amount, "day_of_month": r.day_of_month, "is_active": r.is_active} for r in recs]
        inv_dicts = [{"id": i.id, "customer_id": i.customer_id, "invoice_number": i.invoice_number, "amount": i.amount, "issue_date": i.issue_date, "due_date": i.due_date, "paid_date": i.paid_date, "actual_delay_days": i.actual_delay_days} for i in invs]
        cust_dicts = [{"id": c.id, "name": c.name, "payment_habit": c.payment_habit, "avg_delay_days": c.avg_delay_days, "delay_std_days": c.delay_std_days} for c in custs]

        forecaster = CashFlowForecaster(business_id="biz_001", horizon_days=30)
        res = forecaster.fit_and_forecast(
            business=biz_dict,
            historical_transactions=tx_dicts,
            recurring_payments=rec_dicts,
            historical_invoices=inv_dicts,
            open_invoices=inv_dicts[-10:],
            customers=cust_dicts,
            forecast_start_date=date(2026, 11, 1),
            current_balance=250000.0
        )

        assert res["horizon_days"] == 30
        assert len(res["daily_forecasts"]) == 30

        # Verify confidence interval monotonicity for every single day: p10 <= p50 <= p90
        for d in res["daily_forecasts"]:
            assert d["balance_p10"] <= d["balance_p50"] <= d["balance_p90"]
            assert d["inflow_p10"] <= d["inflow_p50"] <= d["inflow_p90"]
            assert d["outflow_p10"] <= d["outflow_p50"] <= d["outflow_p90"]
            assert "naive_balance" in d
    finally:
        db.close()

def test_danger_days_detection():
    # If starting balance is very low, danger days must trigger
    db = SessionLocal()
    try:
        biz = db.query(Business).filter(Business.id == "biz_001").first()
        txs = db.query(Transaction).filter(Transaction.business_id == "biz_001").all()
        recs = db.query(RecurringPayment).filter(RecurringPayment.business_id == "biz_001").all()
        invs = db.query(Invoice).filter(Invoice.business_id == "biz_001").all()
        custs = db.query(Customer).filter(Customer.business_id == "biz_001").all()

        biz_dict = {"id": biz.id, "category": biz.category, "min_cash_threshold": 50000.0, "initial_balance": 10000.0}
        tx_dicts = [{"id": t.id, "date": t.date, "type": t.type, "category": t.category, "amount": t.amount, "is_banked": t.is_banked, "balance_after": t.balance_after} for t in txs]
        rec_dicts = [{"id": r.id, "title": r.title, "category": r.category, "amount": r.amount, "day_of_month": r.day_of_month, "is_active": r.is_active} for r in recs]
        inv_dicts = [{"id": i.id, "customer_id": i.customer_id, "invoice_number": i.invoice_number, "amount": i.amount, "issue_date": i.issue_date, "due_date": i.due_date, "paid_date": i.paid_date, "actual_delay_days": i.actual_delay_days} for i in invs]
        cust_dicts = [{"id": c.id, "name": c.name, "payment_habit": c.payment_habit, "avg_delay_days": c.avg_delay_days, "delay_std_days": c.delay_std_days} for c in custs]

        forecaster = CashFlowForecaster(business_id="biz_001", horizon_days=30)
        # Starting with only 15,000 (well below 50,000 threshold and with large rent/salary due on 1st & 5th)
        res = forecaster.fit_and_forecast(
            business=biz_dict,
            historical_transactions=tx_dicts,
            recurring_payments=rec_dicts,
            historical_invoices=inv_dicts,
            open_invoices=[],
            customers=cust_dicts,
            forecast_start_date=date(2026, 11, 1),
            current_balance=15000.0
        )

        assert res["danger_days_count"] > 0
        assert res["first_danger_date"] is not None
        assert res["max_shortfall"] > 0
    finally:
        db.close()

def test_backtest_runner():
    res = run_backtest(cutoff_date=date(2026, 10, 1), horizon_days=30, max_businesses=4)
    assert res["businesses_evaluated"] == 4
    metrics = res["metrics"]
    assert "lgbm_wape_avg" in metrics
    assert "naive_wape_avg" in metrics
    assert metrics["p10_p90_interval_coverage_pct"] > 50.0 # Reasonable interval coverage
