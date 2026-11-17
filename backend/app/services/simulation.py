import os
import sys
import json
import uuid
import random
from datetime import date, timedelta
from typing import Dict, List, Any, Optional
import numpy as np

from app.models.database import SessionLocal, Base, engine
from app.models.schema import (
    Business, Transaction, RecurringPayment, Invoice, Customer,
    PredictionLog, ActionRecommendation, DriftEvent
)
from app.ml.forecaster import CashFlowForecaster
from app.services.recommendations import RecommendationEngine
from app.services.closed_loop import ClosedLoopService

class TimeMachineSimulation:
    def __init__(
        self,
        start_date: date = date(2026, 3, 1), # Month 4
        end_date: date = date(2026, 10, 31),  # Month 12
        step_days: int = 7,                  # Replay weekly cycles
        businesses_to_simulate: Optional[List[str]] = None,
        random_seed: int = 42
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.step_days = step_days
        self.businesses_to_simulate = businesses_to_simulate
        random.seed(random_seed)
        np.random.seed(random_seed)

    def run(self) -> Dict[str, Any]:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        rec_engine = RecommendationEngine()
        closed_loop = ClosedLoopService(db)

        # Clear previous simulation prediction/action logs
        db.query(PredictionLog).delete()
        db.query(ActionRecommendation).delete()
        db.query(DriftEvent).delete()
        db.commit()

        # Select businesses
        query = db.query(Business)
        if self.businesses_to_simulate:
            businesses = query.filter(Business.id.in_(self.businesses_to_simulate)).all()
        else:
            # crunch + drift businesses first, then a few healthy ones
            special = query.filter((Business.has_crunch_injected == True) | (Business.has_drift == True)).all()
            special_ids = [b.id for b in special]
            healthy_q = query.filter(~Business.id.in_(special_ids)) if special_ids else query
            businesses = special + healthy_q.limit(6).all()
        biz_ids = [b.id for b in businesses]

        print(f"Starting Time Machine Simulation on {len(businesses)} SMEs...")
        print(f"Timeline: Replaying from {self.start_date} to {self.end_date} (Months 4 to 12) in {self.step_days}-day intervals\n")

        current_sim_date = self.start_date
        weekly_metrics = []
        caught_ids = set()
        actual_crunch_date = {}
        for b in businesses:
            banked = (
                db.query(Transaction)
                .filter(Transaction.business_id == b.id, Transaction.is_banked == True, Transaction.date >= self.start_date)
                .order_by(Transaction.date, Transaction.id)
                .all()
            )
            for t in banked:
                if t.balance_after is not None and t.balance_after < b.min_cash_threshold:
                    actual_crunch_date[b.id] = t.date
                    break
        week_idx = 1

        # Pre-cache customers and recurring
        customers_cache = {}
        recurring_cache = {}
        for b in businesses:
            custs = db.query(Customer).filter(Customer.business_id == b.id).all()
            customers_cache[b.id] = [
                {"id": c.id, "name": c.name, "payment_habit": c.payment_habit, "avg_delay_days": c.avg_delay_days, "delay_std_days": c.delay_std_days}
                for c in custs
            ]
            recs = db.query(RecurringPayment).filter(RecurringPayment.business_id == b.id).all()
            recurring_cache[b.id] = [
                {"id": r.id, "title": r.title, "category": r.category, "amount": r.amount, "day_of_month": r.day_of_month, "is_active": r.is_active}
                for r in recs
            ]

        while current_sim_date <= self.end_date:
            print(f"Simulating Week {week_idx:02d} | Date: {current_sim_date.isoformat()} ...")

            week_errors = []
            week_actuals = []
            drift_events_this_week = 0

            for biz in businesses:
                b_id = biz.id
                biz_dict = {
                    "id": biz.id,
                    "name": biz.name,
                    "category": biz.category,
                    "initial_balance": biz.initial_balance,
                    "min_cash_threshold": biz.min_cash_threshold,
                    "has_crunch_injected": biz.has_crunch_injected,
                    "has_drift": biz.has_drift
                }

                # Step 1: Closed-Loop Evaluation of past predictions that realized
                eval_res = closed_loop.evaluate_realized_predictions(b_id, current_sim_date)

                # Step 2: Check for concept drift and trigger retrain if needed
                drift_res = closed_loop.check_and_record_drift(b_id, current_sim_date, window_days=14, threshold_wape=0.22)
                if drift_res["drift_detected"]:
                    drift_events_this_week += 1

                # Step 3: Evaluate past action outcomes
                closed_loop.evaluate_action_outcomes(b_id, current_sim_date)

                # Step 4: Run 30-Day Forecast based only on data up to current_sim_date
                visible_txs = (
                    db.query(Transaction)
                    .filter(Transaction.business_id == b_id, Transaction.date <= current_sim_date)
                    .all()
                )
                tx_dicts = [
                    {"id": t.id, "date": t.date, "type": t.type, "category": t.category, "amount": t.amount, "is_banked": t.is_banked, "balance_after": t.balance_after}
                    for t in visible_txs
                ]

                # Current balance at current_sim_date
                sorted_banked = sorted([t for t in tx_dicts if t["is_banked"]], key=lambda x: (x["date"], x["id"]))
                curr_balance = sorted_banked[-1]["balance_after"] if sorted_banked else biz.initial_balance

                # Invoices up to current_sim_date
                visible_invoices = (
                    db.query(Invoice)
                    .filter(Invoice.business_id == b_id, Invoice.issue_date <= current_sim_date)
                    .all()
                )
                inv_dicts = [
                    {"id": i.id, "customer_id": i.customer_id, "invoice_number": i.invoice_number, "amount": i.amount, "issue_date": i.issue_date, "due_date": i.due_date, "paid_date": i.paid_date, "actual_delay_days": i.actual_delay_days}
                    for i in visible_invoices
                ]
                open_invs = [inv for inv in inv_dicts if inv["paid_date"] > current_sim_date]

                forecaster = CashFlowForecaster(business_id=b_id, horizon_days=30)
                forecast = forecaster.fit_and_forecast(
                    business=biz_dict,
                    historical_transactions=tx_dicts,
                    recurring_payments=recurring_cache[b_id],
                    historical_invoices=[i for i in inv_dicts if i["paid_date"] <= current_sim_date],
                    open_invoices=open_invs,
                    customers=customers_cache[b_id],
                    forecast_start_date=current_sim_date + timedelta(days=1),
                    current_balance=curr_balance
                )

                # Step 5: Log predictions for next closed-loop evaluation
                closed_loop.log_predictions(b_id, current_sim_date, forecast["daily_forecasts"])

                # Step 6: If Danger Days projected 3-6 weeks ahead, propose recommendations & take action
                danger_days = forecast["danger_days"]
                if danger_days:
                    # Check if this business has an injected crunch in August (Month 10)
                    first_danger_dt = date.fromisoformat(forecast["first_danger_date"])
                    crunch_dt = actual_crunch_date.get(b_id)
                    if crunch_dt and b_id not in caught_ids:
                        lead = (crunch_dt - current_sim_date).days
                        if 14 <= lead <= 30 and abs((first_danger_dt - crunch_dt).days) <= 7:
                            caught_ids.add(b_id)

                    cust_map = {c["id"]: c for c in customers_cache[b_id]}
                    recs = rec_engine.generate_recommendations(
                        business=biz_dict,
                        forecast_result=forecast,
                        open_invoices=open_invs,
                        customers_map=cust_map,
                        simulated_date=current_sim_date
                    )

                    # Simulate business owner accepting the top recommendation (~75% adoption)
                    for idx, rec in enumerate(recs):
                        action_rec = ActionRecommendation(
                            id=rec["id"],
                            business_id=b_id,
                            created_date=current_sim_date,
                            danger_date=rec["danger_date"],
                            action_type=rec["action_type"],
                            title=rec["title"],
                            description=rec.get("description", rec.get("description_en", "")),
                            description_en=rec.get("description_en"),
                            estimated_cost=rec["estimated_cost"],
                            cash_unlocked=rec["cash_unlocked"],
                            net_benefit=rec["net_benefit"],
                            status="accepted" if (idx == 0 and random.random() < 0.75) else "proposed",
                            execution_date=current_sim_date if idx == 0 else None
                        )
                        db.add(action_rec)
                    db.commit()

            # Calculate weekly error on all evaluations resolved in this step
            past_evals = (
                db.query(PredictionLog)
                .filter(
                    PredictionLog.target_date >= (current_sim_date - timedelta(days=self.step_days)),
                    PredictionLog.target_date <= current_sim_date,
                    PredictionLog.status == "evaluated"
                )
                .all()
            )

            if past_evals:
                tot_err = sum(p.absolute_error or 0.0 for p in past_evals)
                tot_act = sum(abs(p.actual_balance or 1.0) for p in past_evals)
                week_wape = float(tot_err / max(tot_act, 1.0))
                week_mape = float(np.mean([p.ape or 0.0 for p in past_evals]))
            else:
                # no evaluated predictions yet (first week): skip instead of inventing a number
                week_idx += 1
                current_sim_date += timedelta(days=self.step_days)
                continue

            weekly_metrics.append({
                "week_number": week_idx,
                "date": current_sim_date.isoformat(),
                "wape": round(week_wape, 4),
                "wape_pct": round(week_wape * 100.0, 2),
                "mape_pct": round(week_mape, 2),
                "drift_retrains": drift_events_this_week
            })

            week_idx += 1
            current_sim_date += timedelta(days=self.step_days)

        # Final evaluation of remaining predictions and actions
        for b_id in biz_ids:
            closed_loop.evaluate_realized_predictions(b_id, self.end_date)
            closed_loop.evaluate_action_outcomes(b_id, self.end_date)

        # Aggregate total actions and outcomes
        all_actions = db.query(ActionRecommendation).all()
        accepted_actions = [a for a in all_actions if a.status in ["accepted", "executed"]]
        averted_actions = [a for a in accepted_actions if a.outcome == "shortfall_averted"]
        mitigated_actions = [a for a in accepted_actions if a.outcome == "shortfall_mitigated"]
        missed_actions = [a for a in accepted_actions if a.outcome == "missed"]

        action_success_rate = round(
            ((len(averted_actions) + len(mitigated_actions)) / max(len(accepted_actions), 1)) * 100.0, 1
        )

        total_drift_events = db.query(DriftEvent).count()
        total_evals = db.query(PredictionLog).filter(PredictionLog.status == "evaluated").count()
        evals_inside = db.query(PredictionLog).filter(PredictionLog.status == "evaluated", PredictionLog.is_inside_interval == True).count()
        final_coverage = round((evals_inside / max(total_evals, 1)) * 100.0, 1)

        # Check crunches: 4 businesses had injected crunches in August
        total_crunches = len(actual_crunch_date)
        crunches_caught = len(caught_ids)
        crunches_missed = total_crunches - crunches_caught
        first_n = weekly_metrics[:4]
        last_n = weekly_metrics[-4:]
        initial_wape = float(np.mean([w["wape_pct"] for w in first_n])) if first_n else None
        final_wape = float(np.mean([w["wape_pct"] for w in last_n])) if last_n else None
        enough = len(weekly_metrics) >= 8
        final_summary = {
            "simulation_period": f"{self.start_date.isoformat()} to {self.end_date.isoformat()} (Months 4 to 12)",
            "sme_count": len(businesses),
            "msme_count": len(businesses),
            "weekly_metrics": weekly_metrics,
            "error_trend": {
                "initial_week_wape_pct": round(initial_wape, 2) if initial_wape is not None else None,
                "final_week_wape_pct": round(final_wape, 2) if final_wape is not None else None,
                "error_reduction_pct": round((initial_wape - final_wape) / max(initial_wape, 1e-4) * 100.0, 1) if enough else None
            },
            "drift_retrains_triggered": total_drift_events,
            "actions_summary": {
                "total_recommendations_generated": len(all_actions),
                "accepted_actions": len(accepted_actions),
                "shortfall_averted": len(averted_actions),
                "shortfall_mitigated": len(mitigated_actions),
                "action_success_rate_pct": action_success_rate
            },
            "crunch_detection": {
                "total_injected_crunches": total_crunches,
                "crunches_caught_early": crunches_caught,
                "crunches_missed": crunches_missed,
                "early_warning_rate_pct": round(crunches_caught / max(total_crunches, 1) * 100.0, 1)
            },
            "interval_coverage_pct": final_coverage
        }
        et = final_summary["error_trend"]
        trend_ok = et["error_reduction_pct"] is not None and et["error_reduction_pct"] > 0

        # Save metrics to reports
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
        os.makedirs(reports_dir, exist_ok=True)

        json_path = os.path.join(reports_dir, "simulation_metrics.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(final_summary, f, indent=2)

        md_path = os.path.join(reports_dir, "simulation_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# CashLoop Closed-Loop Simulation Report: Time Machine Replay\n\n")
            f.write(f"**Replay Window**: {self.start_date} to {self.end_date} (Replaying Month 4 through Month 12 live)\n\n")
            f.write("## 1. Closed-Loop Performance Scorecard\n\n")
            f.write("| Key Success Metric | Realized Result | Target Benchmark | Loop Verification Status |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            f.write(f"| **Forecast Error Trend (WAPE)** | **{et['initial_week_wape_pct']}% -> {et['final_week_wape_pct']}%** | Downward slope | **{'PASS' if trend_ok else 'NOT IMPROVING'}** ({et['error_reduction_pct']}% change) |\n")
            f.write(f"| **Drift Retrains Triggered** | **{total_drift_events} retrains** | Auto-detected on concept shift | Count only |\n")
            f.write(f"| **Action Success Rate** | **{action_success_rate}%** | >= 75% crunches averted | **{'PASS' if action_success_rate >= 75 else 'BELOW TARGET'}** |\n")
            f.write(f"| **Crunches Caught Early (2-4 wk)** | **{crunches_caught} of {total_crunches} caught** | 100% early warning | **{'PASS' if total_crunches and crunches_caught == total_crunches else 'PARTIAL'}** |\n")
            f.write(f"| **Confidence Interval Coverage** | **{final_coverage}%** | Target: 80% | **{'PASS' if 70 <= final_coverage <= 90 else 'OUT OF RANGE'}** |\n\n")
            f.write("## 2. Weekly Forecast Error Trajectory (Adaptation in Action)\n\n")
            f.write("| Week | Simulation Date | WAPE (%) | MAPE (%) | Drift Retrains |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- |\n")
            for w in weekly_metrics:
                f.write(f"| Week {w['week_number']:02d} | `{w['date']}` | **{w['wape_pct']}%** | {w['mape_pct']}% | {w['drift_retrains']} |\n")

        print("\n" + "="*65)
        print("CASHLOOP TIME MACHINE SIMULATION COMPLETE")
        print("="*65)
        print(f"Initial WAPE (first 4 wks): {et['initial_week_wape_pct']}%")
        print(f"Final WAPE (last 4 wks):    {et['final_week_wape_pct']}% (change: {et['error_reduction_pct']}%)")
        print(f"Drift Retrains Triggered: {total_drift_events}")
        print(f"Action Success Rate:      {action_success_rate}% ({len(averted_actions)} averted, {len(mitigated_actions)} mitigated)")
        print(f"Crunches Caught Early:    {crunches_caught}/{total_crunches}")
        print(f"Interval Coverage:        {final_coverage}%")
        print(f"Full Report:              {md_path}")
        print("="*65 + "\n")

        db.close()
        return final_summary

if __name__ == "__main__":
    sim = TimeMachineSimulation()
    sim.run()
