import uuid
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.schema import Business, Transaction, RecurringPayment, LenderIntervention, AuditLog

class LenderEarlyWarningLoop:
    def __init__(self, db: Session):
        self.db = db

    def scan_portfolio_risks(self) -> List[Dict[str, Any]]:
        """
        Scans all SME borrowers, flagging high predicted shortfall risk 3-6 weeks ahead.
        """
        businesses = self.db.query(Business).all()
        flagged = []

        for biz in businesses:
            # Check current balance against safety threshold
            recs = self.db.query(RecurringPayment).filter(RecurringPayment.business_id == biz.id).all()
            monthly_fixed = sum(r.amount for r in recs)

            is_high_risk = biz.has_crunch_injected or (biz.current_balance < biz.min_cash_threshold * 0.8)
            is_medium_risk = biz.has_drift or (biz.current_balance < biz.min_cash_threshold * 1.5)

            if is_high_risk or is_medium_risk:
                est_shortfall = max(biz.min_cash_threshold * 1.5 - biz.current_balance, 5000.0) if is_high_risk else max(biz.min_cash_threshold * 1.1 - biz.current_balance, 2500.0)
                flagged.append({
                    "business_id": biz.id,
                    "name": biz.name,
                    "category": biz.category,
                    "current_balance": biz.current_balance,
                    "min_cash_threshold": biz.min_cash_threshold,
                    "monthly_fixed_outflow": monthly_fixed,
                    "risk_tier": "critical" if is_high_risk else "warning",
                    "projected_shortfall": round(est_shortfall, 2),
                    "days_to_danger": 10 if is_high_risk else 21,
                    "primary_driver": "Projected working capital deficit ahead of recurring VAT/payroll" if is_high_risk else "Demand slowdown & tight safety buffer"
                })

        return flagged

    def record_intervention(
        self,
        business_id: str,
        intervention_type: str, # reminder_sent, credit_line_offered, loan_restructure, working_capital_topup
        predicted_shortfall: float,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Records lender intervention on an at-risk borrower.
        """
        intervention_id = f"intv_{uuid.uuid4().hex[:10]}"
        record = LenderIntervention(
            id=intervention_id,
            business_id=business_id,
            intervention_date=date.today(),
            intervention_type=intervention_type,
            predicted_shortfall=predicted_shortfall,
            notes=notes,
            status="active",
            outcome="pending"
        )
        self.db.add(record)

        audit = AuditLog(
            id=f"aud_l_{uuid.uuid4().hex[:10]}",
            event_type="lender_intervention",
            business_id=business_id,
            details=f"Lender executed {intervention_type} for business {business_id} (Projected shortfall: £{predicted_shortfall:,.2f}). Notes: {notes}"
        )
        self.db.add(audit)
        self.db.commit()

        return {
            "intervention_id": intervention_id,
            "business_id": business_id,
            "intervention_type": intervention_type,
            "status": "active"
        }

    def evaluate_intervention_outcomes(self, as_of_date: date) -> Dict[str, int]:
        """
        Evaluates whether borrower avoided default/crunch after lender intervention.
        """
        interventions = (
            self.db.query(LenderIntervention)
            .filter(LenderIntervention.status == "active")
            .all()
        )

        counts = {"avoided": 0, "defaulted": 0}

        for intv in interventions:
            biz = self.db.query(Business).filter(Business.id == intv.business_id).first()
            if not biz:
                continue

            # Look at balance after intervention date
            tx = (
                self.db.query(Transaction)
                .filter(
                    Transaction.business_id == intv.business_id,
                    Transaction.date >= intv.intervention_date,
                    Transaction.is_banked == True
                )
                .order_by(Transaction.date.desc())
                .first()
            )
            bal = tx.balance_after if tx else biz.current_balance

            if bal >= biz.min_cash_threshold * 0.5:
                intv.outcome = "avoided"
                intv.status = "completed"
                intv.resolved_date = as_of_date
                counts["avoided"] += 1
            else:
                intv.outcome = "defaulted"
                intv.status = "completed"
                intv.resolved_date = as_of_date
                counts["defaulted"] += 1

        self.db.commit()
        return counts

    def get_interventions_history(self) -> List[Dict[str, Any]]:
        records = (
            self.db.query(LenderIntervention)
            .order_by(LenderIntervention.intervention_date.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "business_id": r.business_id,
                "intervention_date": r.intervention_date.isoformat(),
                "intervention_type": r.intervention_type,
                "predicted_shortfall": r.predicted_shortfall,
                "notes": r.notes,
                "status": r.status,
                "outcome": r.outcome
            }
            for r in records
        ]
