import math
import uuid
from datetime import date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.schema import Customer, Invoice, AuditLog

class CustomerBehaviorLoop:
    def __init__(self, db: Session):
        self.db = db

    def record_payment_arrival(
        self,
        customer_id: str,
        invoice_id: str,
        actual_payment_date: date,
        alpha: float = 0.25
    ) -> Dict[str, Any]:
        """
        When a customer invoice is settled, applies Bayesian / exponentially weighted
        updating to sharpen the customer's payment delay distribution.
        """
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

        if not customer or not invoice:
            return {"status": "error", "message": "Customer or invoice not found"}

        # Calculate actual delay
        due_date = invoice.due_date
        actual_delay = (actual_payment_date - due_date).days
        invoice.paid_date = actual_payment_date
        invoice.status = "paid"
        invoice.actual_delay_days = actual_delay

        old_mean = customer.avg_delay_days or 0.0
        old_std = customer.delay_std_days or 3.0
        init_std = customer.initial_delay_std or old_std
        if not customer.initial_delay_std:
            customer.initial_delay_std = old_std
            init_std = old_std

        n = (customer.observations_count or 1) + 1

        # 1. Exponentially weighted mean update
        new_mean = round((1.0 - alpha) * old_mean + alpha * actual_delay, 2)

        # 2. Bayesian uncertainty contraction / sharpening:
        # Precision accumulates with each observation, contracting standard deviation
        contraction = math.sqrt(n / (n + 1.0))
        new_std = round(max(0.5, min(old_std, old_std * contraction)), 2)

        customer.avg_delay_days = new_mean
        customer.delay_std_days = new_std
        customer.observations_count = n

        # Audit log
        audit = AuditLog(
            id=f"aud_cust_{uuid.uuid4().hex[:10]}",
            event_type="customer_profile_updated",
            business_id=customer.business_id,
            details=(
                f"Customer {customer.name} payment received for {invoice.invoice_number} (delay: {actual_delay}d). "
                f"Profile sharpened: mean delay {old_mean}d -> {new_mean}d, std {old_std}d -> {new_std}d (n={n})."
            )
        )
        self.db.add(audit)
        self.db.commit()

        return {
            "customer_id": customer.id,
            "customer_name": customer.name,
            "actual_delay_days": actual_delay,
            "old_mean_delay": old_mean,
            "new_mean_delay": new_mean,
            "old_std_delay": old_std,
            "new_std_delay": new_std,
            "observations_count": n,
            "uncertainty_reduction_pct": round(((init_std - new_std) / init_std) * 100.0, 1)
        }

    def get_sharpening_summary(self, business_id: str) -> List[Dict[str, Any]]:
        """
        Returns the delay profile and uncertainty contraction for all customers of this business.
        """
        customers = self.db.query(Customer).filter(Customer.business_id == business_id).all()
        results = []
        for c in customers:
            init_std = c.initial_delay_std or 5.0
            curr_std = c.delay_std_days or 3.0
            reduction = round(((init_std - curr_std) / max(init_std, 1e-3)) * 100.0, 1)
            results.append({
                "customer_id": c.id,
                "name": c.name,
                "habit": c.payment_habit,
                "observations": c.observations_count or 1,
                "current_avg_delay": c.avg_delay_days,
                "current_std_delay": curr_std,
                "initial_std_delay": init_std,
                "sharpening_gain_pct": max(0.0, reduction)
            })
        return results
