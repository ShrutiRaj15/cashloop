import math
import uuid
from datetime import date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.schema import ActionRecommendation, Transaction, Business, AuditLog

class ActionOutcomeLoop:
    def __init__(self, db: Session):
        self.db = db

    def get_bandit_weights(self, category: str = "kirana") -> Dict[str, Dict[str, float]]:
        """
        Calculates UCB (Upper Confidence Bound) bandit weights per action arm based on historical outcomes.
        """
        actions = self.db.query(ActionRecommendation).all()
        arms = ["early_payment_discount", "delay_supplier_invoice", "credit_line_draw", "chase_customer_invoice"]
        
        arm_stats = {a: {"pulls": 1, "successes": 1} for a in arms} # Laplace smoothing

        for act in actions:
            arm = act.action_type
            if arm not in arm_stats:
                arm_stats[arm] = {"pulls": 1, "successes": 1}
            
            if act.status in ["accepted", "executed"]:
                arm_stats[arm]["pulls"] += 1
                if act.outcome in ["shortfall_averted", "shortfall_mitigated"]:
                    arm_stats[arm]["successes"] += 1

        total_pulls = sum(s["pulls"] for s in arm_stats.values())
        c = 0.8 # Exploration bonus weight

        weights = {}
        for arm, s in arm_stats.items():
            win_rate = s["successes"] / s["pulls"]
            exploration = c * math.sqrt(math.log(max(total_pulls, 2)) / s["pulls"])
            ucb_score = round(win_rate + exploration, 3)
            weights[arm] = {
                "pulls": s["pulls"] - 1, # minus prior
                "successes": s["successes"] - 1,
                "success_rate_pct": round(win_rate * 100.0, 1),
                "ucb_score": ucb_score
            }

        return weights

    def rank_and_score_recommendations(self, recommendations: List[dict], category: str = "kirana") -> List[dict]:
        """
        Re-ranks candidate actions using closed-loop Bandit weights so proven strategies appear first.
        """
        weights = self.get_bandit_weights(category)
        for rec in recommendations:
            arm = rec.get("action_type", "early_payment_discount")
            arm_info = weights.get(arm, {"ucb_score": 1.0, "success_rate_pct": 50.0})
            rec["bandit_arm"] = arm
            rec["bandit_score"] = arm_info["ucb_score"]
            rec["historical_success_rate_pct"] = arm_info["success_rate_pct"]

        # Sort descending by bandit score
        recommendations.sort(key=lambda x: x.get("bandit_score", 1.0), reverse=True)
        return recommendations

    def record_action_decision(self, action_id: str, decision: str) -> Dict[str, Any]:
        """
        Records business owner decision: accepted, rejected, or done.
        """
        action = self.db.query(ActionRecommendation).filter(ActionRecommendation.id == action_id).first()
        if not action:
            return {"status": "error", "message": "Action recommendation not found"}

        action.status = decision
        if decision in ["accepted", "executed"]:
            action.execution_date = date.today()

        audit = AuditLog(
            id=f"aud_act_{action_id}",
            event_type="action_decision_recorded",
            business_id=action.business_id,
            details=f"Owner {decision} recommended action '{action.title}' (Arm: {action.action_type}, unlocked: ₹{action.cash_unlocked})."
        )
        self.db.add(audit)
        self.db.commit()

        return {
            "action_id": action.id,
            "title": action.title,
            "new_status": action.status,
            "bandit_arm": action.action_type
        }

    def evaluate_matured_actions(self, current_date: date) -> Dict[str, int]:
        """
        Evaluates whether accepted actions whose danger_date has passed successfully averted the cash shortfall.
        """
        due_actions = (
            self.db.query(ActionRecommendation)
            .filter(
                ActionRecommendation.danger_date <= current_date,
                ActionRecommendation.outcome == None
            )
            .all()
        )

        counts = {"averted": 0, "mitigated": 0, "missed": 0}

        for act in due_actions:
            biz = self.db.query(Business).filter(Business.id == act.business_id).first()
            thresh = biz.min_cash_threshold if biz else 25000.0

            # Find actual balance on danger date
            tx = (
                self.db.query(Transaction)
                .filter(
                    Transaction.business_id == act.business_id,
                    Transaction.date <= act.danger_date,
                    Transaction.is_banked == True
                )
                .order_by(Transaction.date.desc(), Transaction.id.desc())
                .first()
            )
            actual_balance = tx.balance_after if tx else 0.0

            if act.status in ["accepted", "executed"]:
                if actual_balance >= thresh:
                    act.outcome = "shortfall_averted"
                    counts["averted"] += 1
                elif actual_balance >= 0:
                    act.outcome = "shortfall_mitigated"
                    counts["mitigated"] += 1
                else:
                    act.outcome = "missed"
                    counts["missed"] += 1
            else:
                act.outcome = "missed"
                counts["missed"] += 1

        self.db.commit()
        return counts
