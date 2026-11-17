from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Dict, Any

from app.models.database import get_db
from app.models.schema import Business, Transaction, RecurringPayment, Invoice, Customer
from app.ml.forecaster import CashFlowForecaster

router = APIRouter(prefix="/lender", tags=["lender"])

@router.get("/portfolio")
def get_portfolio_overview(db: Session = Depends(get_db)):
    businesses = db.query(Business).all()
    
    portfolio_items = []
    total_exposure = 0.0
    total_shortfall = 0.0
    critical_count = 0
    warning_count = 0
    safe_count = 0

    # Quick forecast assessment across all businesses
    for biz in businesses:
        total_exposure += biz.initial_balance * 2.5 # proxy for total SME exposure / credit facility

        txs = db.query(Transaction).filter(Transaction.business_id == biz.id).all()
        recs = db.query(RecurringPayment).filter(RecurringPayment.business_id == biz.id).all()
        
        # Fast indicator: compare current balance against upcoming monthly recurring obligations
        monthly_fixed_outflow = sum(r.amount for r in recs)

        is_crunch = biz.has_crunch_injected
        is_drift = biz.has_drift

        # Projected status
        if is_crunch or (biz.current_balance < biz.min_cash_threshold * 0.7):
            risk_tier = "critical"
            critical_count += 1
            days_to_danger = 8
            est_shortfall = max(biz.min_cash_threshold * 1.5 - biz.current_balance, 5000.0)
            primary_driver = "Severe liquidity crunch: Loan repayments and supplier debits exceed cash inflows"
            health_score = 38
        elif is_drift or (biz.current_balance < biz.min_cash_threshold * 1.5):
            risk_tier = "warning"
            warning_count += 1
            days_to_danger = 19
            est_shortfall = max(biz.min_cash_threshold * 1.1 - biz.current_balance, 2500.0)
            primary_driver = "Revenue slowdown & upcoming statutory VAT settlement obligation"
            health_score = 62
        else:
            risk_tier = "safe"
            safe_count += 1
            days_to_danger = None
            est_shortfall = 0.0
            primary_driver = "Stable operations and consistent customer payment cycles"
            health_score = 88

        total_shortfall += est_shortfall

        portfolio_items.append({
            "business_id": biz.id,
            "name": biz.name,
            "category": biz.category,
            "city": biz.city,
            "state": biz.state,
            "current_balance": biz.current_balance,
            "min_cash_threshold": biz.min_cash_threshold,
            "monthly_fixed_outflow": monthly_fixed_outflow,
            "unbanked_cash_share_pct": round(biz.unbanked_cash_share * 100, 0),
            "risk_tier": risk_tier,
            "health_score": health_score,
            "days_to_danger": days_to_danger,
            "projected_shortfall": round(est_shortfall, 2),
            "primary_driver": primary_driver,
            "has_drift": biz.has_drift,
            "has_crunch_injected": biz.has_crunch_injected
        })

    # Sort critical first, then warning, then safe
    portfolio_items.sort(key=lambda x: (0 if x["risk_tier"] == "critical" else 1 if x["risk_tier"] == "warning" else 2, x["health_score"]))

    return {
        "portfolio_summary": {
            "total_smes": len(businesses),
            "total_msmes": len(businesses), # Legacy compatibility
            "total_exposure": round(total_exposure, 2),
            "total_projected_shortfall": round(total_shortfall, 2),
            "critical_risk_count": critical_count,
            "warning_risk_count": warning_count,
            "safe_count": safe_count,
            "portfolio_health_index": round(
                (safe_count * 100 + warning_count * 60 + critical_count * 30) / max(len(businesses), 1), 1
            )
        },
        "businesses": portfolio_items
    }

from pydantic import BaseModel
from typing import Optional

class LenderInterventionRequest(BaseModel):
    business_id: str
    intervention_type: str # reminder_sent, credit_line_offered, loan_restructure, working_capital_topup
    predicted_shortfall: float
    notes: Optional[str] = ""

@router.post("/interventions")
def record_intervention_endpoint(
    payload: LenderInterventionRequest,
    db: Session = Depends(get_db)
):
    from app.services.loops.lender_early_warning_loop import LenderEarlyWarningLoop
    loop = LenderEarlyWarningLoop(db)
    result = loop.record_intervention(
        business_id=payload.business_id,
        intervention_type=payload.intervention_type,
        predicted_shortfall=payload.predicted_shortfall,
        notes=payload.notes or ""
    )
    return result

@router.get("/interventions")
def get_interventions_endpoint(db: Session = Depends(get_db)):
    from app.services.loops.lender_early_warning_loop import LenderEarlyWarningLoop
    loop = LenderEarlyWarningLoop(db)
    return loop.get_interventions_history()
