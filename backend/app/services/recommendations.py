import uuid
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from app.services.llm import get_llm_service

class RecommendationEngine:
    def __init__(self):
        self.llm = get_llm_service()

    def generate_recommendations(
        self,
        business: dict,
        forecast_result: dict,
        open_invoices: List[dict],
        customers_map: Dict[str, dict],
        simulated_date: Optional[date] = None
    ) -> List[dict]:
        danger_days = forecast_result.get("danger_days", [])
        if not danger_days:
            return []

        first_danger = danger_days[0]
        danger_date_str = first_danger["date"]
        danger_date = date.fromisoformat(danger_date_str) if isinstance(danger_date_str, str) else danger_date_str
        sim_date = simulated_date or (danger_date - timedelta(days=14))
        shortfall = forecast_result.get("max_shortfall", 20000.0)
        biz_name = business.get("name", "Store")

        recommendations = []

        # Action 1: Early Payment Discount on an Open Invoice
        # Find largest open invoice with a customer
        if open_invoices:
            sorted_invoices = sorted(open_invoices, key=lambda x: x.get("amount", 0.0), reverse=True)
            top_inv = sorted_invoices[0]
            cust = customers_map.get(top_inv.get("customer_id"), {})
            cust_name = cust.get("name", "Key Customer")
            inv_amt = float(top_inv.get("amount", 25000.0))

            discount_rate = 0.015 # 1.5% discount
            cost = round(inv_amt * discount_rate, 2)
            unlocked = round(inv_amt - cost, 2)
            net_benefit = round(unlocked - cost, 2)

            act_id = f"act_{uuid.uuid4().hex[:10]}"
            title = f"Offer 1.5% Early-Payment Discount to {cust_name}"
            desc_en = (
                f"Offer {cust_name} a 1.5% prompt settlement rebate on invoice {top_inv.get('invoice_number', 'pending')} "
                f"(£{inv_amt:,.2f}) to accelerate receipt by 12 days before your danger day on {danger_date_str}."
            )

            recommendations.append({
                "id": act_id,
                "business_id": business.get("id"),
                "created_date": sim_date,
                "danger_date": danger_date,
                "action_type": "early_payment_discount",
                "title": title,
                "description": desc_en,
                "description_en": desc_en,
                "estimated_cost": cost,
                "cash_unlocked": unlocked,
                "net_benefit": net_benefit,
                "status": "proposed",
                "invoice_id": top_inv.get("id"),
                "target_name": cust_name
            })

        # Action 2: Split / Delay Upcoming Supplier Outflow
        rec_cost = 0.0
        defer_amount = round(min(shortfall * 1.1, 15000.0), 2)
        act_id_2 = f"act_{uuid.uuid4().hex[:10]}"
        title_2 = "Split Trade Supplier Invoice into Two 10-Day Tranches"
        desc_en_2 = (
            f"Negotiate with primary trade supplier to pay 50% now and remaining £{defer_amount:,.2f} after 10 days, "
            f"bridging your cash balance across the danger window around {danger_date_str} at zero extra cost."
        )

        recommendations.append({
            "id": act_id_2,
            "business_id": business.get("id"),
            "created_date": sim_date,
            "danger_date": danger_date,
            "action_type": "delay_supplier_invoice",
            "title": title_2,
            "description": desc_en_2,
            "description_en": desc_en_2,
            "estimated_cost": rec_cost,
            "cash_unlocked": defer_amount,
            "net_benefit": defer_amount,
            "status": "proposed",
            "target_name": "Primary Trade Merchant"
        })

        # Action 3: Pre-Approved SME Working Capital Facility Draw
        draw_amount = round(shortfall + 3000.0, 2)
        # 14 days interest at 9.5% p.a.
        interest_cost = round(draw_amount * (0.095 / 365) * 14, 2)
        act_id_3 = f"act_{uuid.uuid4().hex[:10]}"
        title_3 = f"Draw Short-Term SME Working Capital Facility (£{draw_amount:,.2f})"
        desc_en_3 = (
            f"Utilise pre-approved revolving credit facility for 14 days. Unlocks £{draw_amount:,.2f} of immediate cushion "
            f"for an estimated interest fee of £{interest_cost:,.2f}."
        )

        recommendations.append({
            "id": act_id_3,
            "business_id": business.get("id"),
            "created_date": sim_date,
            "danger_date": danger_date,
            "action_type": "credit_line_draw",
            "title": title_3,
            "description": desc_en_3,
            "description_en": desc_en_3,
            "estimated_cost": interest_cost,
            "cash_unlocked": draw_amount,
            "net_benefit": round(draw_amount - interest_cost, 2),
            "status": "proposed",
            "target_name": "Commercial Bank Overdraft / Invoice Finance"
        })

        return recommendations
