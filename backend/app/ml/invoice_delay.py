import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.linear_model import QuantileRegressor

class InvoiceDelayModel:
    def __init__(self):
        self.models: Dict[float, any] = {}
        self.is_fitted = False
        self.quantiles = [0.10, 0.50, 0.90]
        self.habit_map = {
            "disciplined": 0,
            "chronic_late": 1,
            "erratic": 2,
            "seasonal": 3
        }

    def _extract_features(self, invoices: List[dict], customers_map: Dict[str, dict]) -> Tuple[pd.DataFrame, np.ndarray]:
        rows = []
        targets = []
        for inv in invoices:
            cust_id = inv.get("customer_id")
            cust = customers_map.get(cust_id, {})
            habit = cust.get("payment_habit", "disciplined")
            habit_num = self.habit_map.get(habit, 0)

            issue_dt = inv.get("issue_date")
            due_dt = inv.get("due_date")
            if isinstance(issue_dt, str):
                issue_dt = date.fromisoformat(issue_dt)
            if isinstance(due_dt, str):
                due_dt = date.fromisoformat(due_dt)

            term_days = (due_dt - issue_dt).days if (due_dt and issue_dt) else 30
            amount = float(inv.get("amount", 10000.0))

            feat = {
                "log_amount": math.log1p(amount),
                "term_days": float(term_days),
                "cust_avg_delay": float(cust.get("avg_delay_days", 0.0)),
                "cust_delay_std": float(cust.get("delay_std_days", 3.0)),
                "habit_num": habit_num,
                "due_day_of_month": float(due_dt.day if due_dt else 15),
                "due_month": float(due_dt.month if due_dt else 6),
                "is_festive_month": 1.0 if (due_dt and due_dt.month in [10, 11, 3]) else 0.0,
            }
            rows.append(feat)

            if "actual_delay_days" in inv and inv["actual_delay_days"] is not None:
                targets.append(float(inv["actual_delay_days"]))
            else:
                targets.append(0.0)

        df = pd.DataFrame(rows)
        y = np.array(targets)
        return df, y

    def fit(self, historical_invoices: List[dict], customers: List[dict]):
        customers_map = {c["id"]: c for c in customers}
        paid_invoices = [inv for inv in historical_invoices if inv.get("actual_delay_days") is not None]

        if len(paid_invoices) < 20:
            # Not enough data for LGBM, use heuristic fallback
            self.is_fitted = False
            return

        X, y = self._extract_features(paid_invoices, customers_map)

        for q in self.quantiles:
            model = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=60,
                learning_rate=0.08,
                num_leaves=15,
                min_child_samples=3,
                verbose=-1,
                random_state=42
            )
            model.fit(X, y)
            self.models[q] = model

        self.is_fitted = True

    def predict_delays(self, open_invoices: List[dict], customers: List[dict]) -> List[dict]:
        customers_map = {c["id"]: c for c in customers}
        if not open_invoices:
            return []

        X, _ = self._extract_features(open_invoices, customers_map)
        results = []

        if self.is_fitted:
            preds_p10 = self.models[0.10].predict(X)
            preds_p50 = self.models[0.50].predict(X)
            preds_p90 = self.models[0.90].predict(X)
        else:
            # Fallback to customer habits
            preds_p10, preds_p50, preds_p90 = [], [], []
            for inv in open_invoices:
                cust = customers_map.get(inv.get("customer_id"), {})
                avg_d = float(cust.get("avg_delay_days", 5.0))
                std_d = float(cust.get("delay_std_days", 3.0))
                preds_p10.append(max(-2.0, avg_d - 1.28 * std_d))
                preds_p50.append(max(0.0, avg_d))
                preds_p90.append(max(0.0, avg_d + 1.28 * std_d))
            preds_p10 = np.array(preds_p10)
            preds_p50 = np.array(preds_p50)
            preds_p90 = np.array(preds_p90)

        for idx, inv in enumerate(open_invoices):
            due_dt = inv.get("due_date")
            if isinstance(due_dt, str):
                due_dt = date.fromisoformat(due_dt)

            d10 = int(round(preds_p10[idx]))
            d50 = int(round(preds_p50[idx]))
            d90 = int(round(preds_p90[idx]))

            # Guarantee quantile order
            d10 = min(d10, d50)
            d90 = max(d90, d50)

            exp_date = due_dt + timedelta(days=d50) if due_dt else None
            p10_date = due_dt + timedelta(days=d10) if due_dt else None
            p90_date = due_dt + timedelta(days=d90) if due_dt else None

            results.append({
                "invoice_id": inv.get("id"),
                "invoice_number": inv.get("invoice_number"),
                "amount": float(inv.get("amount", 0.0)),
                "due_date": due_dt,
                "delay_p10": d10,
                "delay_p50": d50,
                "delay_p90": d90,
                "expected_payment_date": exp_date,
                "p10_payment_date": p10_date,
                "p90_payment_date": p90_date,
                "customer_name": customers_map.get(inv.get("customer_id"), {}).get("name", "Unknown"),
                "payment_habit": customers_map.get(inv.get("customer_id"), {}).get("payment_habit", "disciplined")
            })

        return results

    def get_daily_inflows_from_open_invoices(
        self,
        open_invoices: List[dict],
        customers: List[dict],
        forecast_dates: List[date]
    ) -> Dict[str, Dict[date, float]]:
        """
        Projects daily cash inflow by date across the forecast horizon for p10, p50, p90.
        """
        preds = self.predict_delays(open_invoices, customers)
        date_set = set(forecast_dates)

        inflows_p10 = {d: 0.0 for d in forecast_dates}
        inflows_p50 = {d: 0.0 for d in forecast_dates}
        inflows_p90 = {d: 0.0 for d in forecast_dates}

        for p in preds:
            amt = p["amount"]
            # p50 expected date
            if p["expected_payment_date"] in date_set:
                inflows_p50[p["expected_payment_date"]] += amt
            elif p["expected_payment_date"] and p["expected_payment_date"] < forecast_dates[0]:
                # If already overdue relative to forecast start, expected soon on day 1 or 2
                inflows_p50[forecast_dates[0]] += amt

            # p10 (optimistic / earlier)
            if p["p10_payment_date"] in date_set:
                inflows_p10[p["p10_payment_date"]] += amt
            elif p["p10_payment_date"] and p["p10_payment_date"] < forecast_dates[0]:
                inflows_p10[forecast_dates[0]] += amt

            # p90 (delayed)
            if p["p90_payment_date"] in date_set:
                inflows_p90[p["p90_payment_date"]] += amt

        return {
            "p10": inflows_p10,
            "p50": inflows_p50,
            "p90": inflows_p90,
        }
