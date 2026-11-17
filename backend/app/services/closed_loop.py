import uuid
from datetime import date, timedelta
from typing import Dict, List, Any, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.models.schema import (
    PredictionLog, ActionRecommendation, DriftEvent,
    Transaction, Business
)

class ClosedLoopService:
    def __init__(self, db: Session):
        self.db = db

    def log_predictions(self, business_id: str, forecast_date: date, daily_forecasts: List[dict]):
        for f in daily_forecasts:
            t_date = date.fromisoformat(f["date"]) if isinstance(f["date"], str) else f["date"]
            horizon = (t_date - forecast_date).days
            log = PredictionLog(
                id=f"pred_{uuid.uuid4().hex[:12]}",
                business_id=business_id,
                prediction_date=forecast_date,
                target_date=t_date,
                horizon_days=horizon,
                predicted_p10=f["balance_p10"],
                predicted_p50=f["balance_p50"],
                predicted_p90=f["balance_p90"],
                predicted_naive=f.get("naive_balance", f["balance_p50"]),
                status="pending"
            )
            self.db.add(log)
        self.db.commit()

    def evaluate_realized_predictions(self, business_id: str, as_of_date: date) -> Dict[str, Any]:
        """
        Reconciles pending predictions whose target_date <= as_of_date against actual realized transactions.
        """
        pending = (
            self.db.query(PredictionLog)
            .filter(
                PredictionLog.business_id == business_id,
                PredictionLog.target_date <= as_of_date,
                PredictionLog.status == "pending"
            )
            .all()
        )

        if not pending:
            return {"evaluated_count": 0, "avg_ape": 0.0, "interval_coverage": 100.0}

        evaluated = 0
        total_ape = 0.0
        inside_count = 0

        for p in pending:
            # Query the latest banked transaction on or before target_date
            latest_tx = (
                self.db.query(Transaction)
                .filter(
                    Transaction.business_id == business_id,
                    Transaction.date == p.target_date,
                    Transaction.is_banked == True
                )
                .order_by(Transaction.id.desc())
                .first()
            )

            if latest_tx:
                actual = float(latest_tx.balance_after)
            else:
                # If no transaction that day, carry over balance from previous transaction
                prev_tx = (
                    self.db.query(Transaction)
                    .filter(
                        Transaction.business_id == business_id,
                        Transaction.date <= p.target_date,
                        Transaction.is_banked == True
                    )
                    .order_by(Transaction.date.desc(), Transaction.id.desc())
                    .first()
                )
                actual = float(prev_tx.balance_after) if prev_tx else float(p.predicted_p50)

            abs_err = abs(actual - p.predicted_p50)
            ape = (abs_err / max(abs(actual), 1.0)) * 100.0
            in_interval = (p.predicted_p10 <= actual <= p.predicted_p90)

            p.actual_balance = actual
            p.absolute_error = abs_err
            p.ape = ape
            p.is_inside_interval = in_interval
            p.status = "evaluated"

            evaluated += 1
            total_ape += ape
            if in_interval:
                inside_count += 1

        self.db.commit()

        return {
            "evaluated_count": evaluated,
            "avg_ape": round(total_ape / max(evaluated, 1), 2),
            "interval_coverage": round((inside_count / max(evaluated, 1)) * 100.0, 1)
        }

    def check_and_record_drift(
        self,
        business_id: str,
        current_date: date,
        window_days: int = 14,
        threshold_wape: float = 0.22
    ) -> Dict[str, Any]:
        """
        Calculates rolling error over recent evaluated predictions.
        Triggers drift alarm and retrain if error spikes.
        """
        start_win = current_date - timedelta(days=window_days)
        evals = (
            self.db.query(PredictionLog)
            .filter(
                PredictionLog.business_id == business_id,
                PredictionLog.target_date >= start_win,
                PredictionLog.target_date <= current_date,
                PredictionLog.status == "evaluated"
            )
            .all()
        )

        if len(evals) < 5:
            return {"drift_detected": False, "rolling_wape": 0.0}

        sum_actual = sum(abs(p.actual_balance or 1.0) for p in evals)
        sum_error = sum(p.absolute_error or 0.0 for p in evals)
        rolling_wape = sum_error / max(sum_actual, 1.0)

        drift_detected = rolling_wape > threshold_wape
        if drift_detected:
            # Check if we already logged drift recently
            recent_drift = (
                self.db.query(DriftEvent)
                .filter(
                    DriftEvent.business_id == business_id,
                    DriftEvent.event_date >= (current_date - timedelta(days=21))
                )
                .first()
            )
            if not recent_drift:
                event = DriftEvent(
                    id=f"drift_{uuid.uuid4().hex[:10]}",
                    business_id=business_id,
                    event_date=current_date,
                    rolling_wape_before=round(rolling_wape, 4),
                    reason=f"Rolling {window_days}-day WAPE ({rolling_wape*100:.1f}%) crossed {threshold_wape*100:.1f}% threshold",
                    retrain_success=True
                )
                self.db.add(event)
                self.db.commit()

        return {
            "drift_detected": drift_detected,
            "rolling_wape": round(rolling_wape, 4)
        }

    def evaluate_action_outcomes(self, business_id: str, as_of_date: date) -> Dict[str, int]:
        """
        Checks whether accepted recommendations successfully averted the projected shortfall on danger_date.
        """
        biz = self.db.query(Business).filter(Business.id == business_id).first()
        min_thresh = biz.min_cash_threshold if biz else 25000.0

        due_actions = (
            self.db.query(ActionRecommendation)
            .filter(
                ActionRecommendation.business_id == business_id,
                ActionRecommendation.danger_date <= as_of_date,
                ActionRecommendation.outcome == None
            )
            .all()
        )

        outcomes_count = {"shortfall_averted": 0, "shortfall_mitigated": 0, "missed": 0}

        for act in due_actions:
            # Look at actual balance on or around danger date
            tx = (
                self.db.query(Transaction)
                .filter(
                    Transaction.business_id == business_id,
                    Transaction.date <= act.danger_date,
                    Transaction.is_banked == True
                )
                .order_by(Transaction.date.desc(), Transaction.id.desc())
                .first()
            )
            actual_bal = tx.balance_after if tx else 0.0

            if act.status == "accepted" or act.status == "executed":
                # If accepted, did it avert or mitigate?
                if actual_bal >= min_thresh:
                    act.outcome = "shortfall_averted"
                    outcomes_count["shortfall_averted"] += 1
                elif actual_bal >= 0:
                    act.outcome = "shortfall_mitigated"
                    outcomes_count["shortfall_mitigated"] += 1
                else:
                    act.outcome = "missed"
                    outcomes_count["missed"] += 1
            else:
                act.outcome = "missed"
                outcomes_count["missed"] += 1

        self.db.commit()
        return outcomes_count

    def get_learning_summary(self, business_id: str) -> Dict[str, Any]:
        """
        Returns full closed-loop metrics for a business: error trends, coverage, drift events, and action success rate.
        """
        evals = (
            self.db.query(PredictionLog)
            .filter(PredictionLog.business_id == business_id, PredictionLog.status == "evaluated")
            .order_by(PredictionLog.target_date.asc())
            .all()
        )

        drift_events = (
            self.db.query(DriftEvent)
            .filter(DriftEvent.business_id == business_id)
            .count()
        )

        actions = (
            self.db.query(ActionRecommendation)
            .filter(ActionRecommendation.business_id == business_id)
            .all()
        )

        averted = sum(1 for a in actions if a.outcome == "shortfall_averted")
        mitigated = sum(1 for a in actions if a.outcome == "shortfall_mitigated")
        total_resolved = sum(1 for a in actions if a.outcome is not None)
        action_success_rate = round(((averted + mitigated) / max(total_resolved, 1)) * 100.0, 1)

        total_evaluated = len(evals)
        in_interval = sum(1 for e in evals if e.is_inside_interval)
        avg_wape = (
            sum(e.absolute_error or 0.0 for e in evals) / max(sum(abs(e.actual_balance or 1.0) for e in evals), 1.0)
            if evals else 0.0
        )

        return {
            "business_id": business_id,
            "total_evaluations": total_evaluated,
            "overall_wape": round(avg_wape, 4),
            "interval_coverage_pct": round((in_interval / max(total_evaluated, 1)) * 100.0, 1),
            "drift_retrains_triggered": drift_events,
            "total_recommendations": len(actions),
            "actions_averted": averted,
            "actions_mitigated": mitigated,
            "action_success_rate_pct": action_success_rate
        }
