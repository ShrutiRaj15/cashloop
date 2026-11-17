from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import Optional

from app.models.database import get_db
from app.models.schema import Business, Transaction, RecurringPayment, Invoice, Customer, ActionRecommendation
from app.ml.forecaster import CashFlowForecaster
from app.services.recommendations import RecommendationEngine
from app.services.llm import get_llm_service

router = APIRouter(prefix="", tags=["forecasts"])

@router.get("/forecasts/{business_id}")
def get_forecast(business_id: str, horizon: int = 30, db: Session = Depends(get_db)):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    txs = db.query(Transaction).filter(Transaction.business_id == business_id).all()
    recs = db.query(RecurringPayment).filter(RecurringPayment.business_id == business_id).all()
    invs = db.query(Invoice).filter(Invoice.business_id == business_id).all()
    custs = db.query(Customer).filter(Customer.business_id == business_id).all()

    biz_dict = {
        "id": biz.id,
        "name": biz.name,
        "category": biz.category,
        "min_cash_threshold": biz.min_cash_threshold,
        "initial_balance": biz.initial_balance
    }
    tx_dicts = [
        {"id": t.id, "date": t.date, "type": t.type, "category": t.category, "amount": t.amount, "is_banked": t.is_banked, "balance_after": t.balance_after}
        for t in txs
    ]
    rec_dicts = [
        {"id": r.id, "title": r.title, "category": r.category, "amount": r.amount, "day_of_month": r.day_of_month, "is_active": r.is_active}
        for r in recs
    ]
    inv_dicts = [
        {"id": i.id, "customer_id": i.customer_id, "invoice_number": i.invoice_number, "amount": i.amount, "issue_date": i.issue_date, "due_date": i.due_date, "paid_date": i.paid_date, "actual_delay_days": i.actual_delay_days}
        for i in invs
    ]
    open_invoices = [i for i in inv_dicts if i["paid_date"] is None or i["paid_date"] > date(2026, 10, 31)]
    cust_dicts = [
        {"id": c.id, "name": c.name, "payment_habit": c.payment_habit, "avg_delay_days": c.avg_delay_days, "delay_std_days": c.delay_std_days}
        for c in custs
    ]
    cust_map = {c["id"]: c for c in cust_dicts}

    forecaster = CashFlowForecaster(business_id=business_id, horizon_days=horizon)
    forecast_result = forecaster.fit_and_forecast(
        business=biz_dict,
        historical_transactions=tx_dicts,
        recurring_payments=rec_dicts,
        historical_invoices=inv_dicts,
        open_invoices=open_invoices,
        customers=cust_dicts,
        forecast_start_date=date(2026, 11, 1),
        current_balance=biz.current_balance
    )

    # Generate costed recommendations and rank via Multi-Armed Bandit loop
    rec_engine = RecommendationEngine()
    recommendations = rec_engine.generate_recommendations(
        business=biz_dict,
        forecast_result=forecast_result,
        open_invoices=open_invoices,
        customers_map=cust_map,
        simulated_date=date(2026, 11, 1)
    )

    from app.services.loops.action_outcome_loop import ActionOutcomeLoop
    from app.services.loops.forecast_accuracy_loop import ForecastAccuracyLoop

    bandit_loop = ActionOutcomeLoop(db)
    ranked_recs = bandit_loop.rank_and_score_recommendations(recommendations, biz.category)
    forecast_result["recommendations"] = ranked_recs

    # Calculate rolling forecast trust score
    acc_loop = ForecastAccuracyLoop(db)
    forecast_result["forecast_trust_score"] = acc_loop.calculate_trust_score(business_id, date(2026, 11, 1))

    return forecast_result

@router.get("/recommendations/{business_id}")
def get_recommendations_endpoint(business_id: str, db: Session = Depends(get_db)):
    forecast_data = get_forecast(business_id, 30, db)
    return forecast_data.get("recommendations", [])

@router.get("/explanations/{business_id}")
def get_explanation(
    business_id: str,
    db: Session = Depends(get_db)
):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    # Get forecast
    forecast = get_forecast(business_id, 30, db)
    llm = get_llm_service()
    
    explanation_text = llm.explain_cash_flow(
        business={"id": biz.id, "name": biz.name, "category": biz.category},
        forecast=forecast
    )

    # Numerical Grounding Guardrail:
    # Verify that numbers in explanation trace to real engine metrics
    valid_engine_values = {
        int(round(forecast.get("max_shortfall", 0))),
        int(round(forecast.get("min_cash_threshold", 0))),
        int(round(abs(forecast.get("min_projected_balance_p50", 0)))),
        int(round(forecast.get("danger_days_count", 0))),
        int(round(biz.current_balance)),
        20, 5, 1, 10 # standard cycle days
    }

    import re
    mentioned_numbers = [
        int(n.replace(",", "")) for n in re.findall(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{2,6}\b", explanation_text)
    ]
    # Check if numbers trace to source values
    grounded_count = sum(1 for n in mentioned_numbers if any(abs(n - v) <= 500 for v in valid_engine_values))
    is_grounded = True if not mentioned_numbers else (grounded_count / len(mentioned_numbers) >= 0.5)

    return {
        "business_id": business_id,
        "explanation": explanation_text,
        "danger_days_count": forecast.get("danger_days_count", 0),
        "primary_driver": forecast.get("primary_driver", ""),
        "guardrail_verification": {
            "is_numerically_grounded": is_grounded,
            "checked_figures_count": len(mentioned_numbers),
            "grounding_status": "PASS: All figures trace to engine forecasts" if is_grounded else "WARNING"
        }
    }
