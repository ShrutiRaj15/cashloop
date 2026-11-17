from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.models.database import get_db
from app.models.schema import ActionRecommendation, DriftEvent, PredictionLog
from app.services.closed_loop import ClosedLoopService

router = APIRouter(prefix="", tags=["closed_loop"])

class ActionRecordRequest(BaseModel):
    status: str # accepted, rejected, executed

@router.get("/closed-loop/{business_id}")
def get_closed_loop_status(business_id: str, db: Session = Depends(get_db)):
    service = ClosedLoopService(db)
    summary = service.get_learning_summary(business_id)

    # Fetch recent drift events
    drifts = (
        db.query(DriftEvent)
        .filter(DriftEvent.business_id == business_id)
        .order_by(DriftEvent.event_date.desc())
        .limit(5)
        .all()
    )

    # Fetch recent action recommendations
    actions = (
        db.query(ActionRecommendation)
        .filter(ActionRecommendation.business_id == business_id)
        .order_by(ActionRecommendation.created_date.desc())
        .limit(10)
        .all()
    )

    summary["drift_events"] = [
        {
            "id": d.id,
            "event_date": d.event_date.isoformat(),
            "rolling_wape_before": d.rolling_wape_before,
            "reason": d.reason,
            "retrain_success": d.retrain_success
        }
        for d in drifts
    ]

    summary["actions"] = [
        {
            "id": a.id,
            "created_date": a.created_date.isoformat(),
            "danger_date": a.danger_date.isoformat(),
            "action_type": a.action_type,
            "title": a.title,
            "description": a.description or a.description_en,
            "description_en": a.description_en or a.description,
            "estimated_cost": a.estimated_cost,
            "cash_unlocked": a.cash_unlocked,
            "net_benefit": a.net_benefit,
            "bandit_arm": a.bandit_arm,
            "bandit_score": a.bandit_score,
            "status": a.status,
            "outcome": a.outcome
        }
        for a in actions
    ]

    from app.services.loops.customer_behavior_loop import CustomerBehaviorLoop
    from app.services.loops.forecast_accuracy_loop import ForecastAccuracyLoop

    cust_loop = CustomerBehaviorLoop(db)
    summary["customer_sharpening"] = cust_loop.get_sharpening_summary(business_id)

    acc_loop = ForecastAccuracyLoop(db)
    summary["forecast_trust_score"] = acc_loop.calculate_trust_score(business_id, date(2026, 11, 1))

    return summary

@router.post("/actions/{action_id}/record")
def record_action_decision(action_id: str, payload: ActionRecordRequest, db: Session = Depends(get_db)):
    action = db.query(ActionRecommendation).filter(ActionRecommendation.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action recommendation not found")

    action.status = payload.status
    if payload.status in ["accepted", "executed"]:
        action.execution_date = date.today()
    db.commit()

    return {
        "status": "success",
        "action_id": action_id,
        "new_status": action.status,
        "execution_date": action.execution_date.isoformat() if action.execution_date else None
    }
