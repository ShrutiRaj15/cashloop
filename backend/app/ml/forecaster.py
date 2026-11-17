import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import lightgbm as lgb

from app.ml.features import (
    build_calendar_features_df,
    build_daily_timeseries_df
)
from app.ml.invoice_delay import InvoiceDelayModel

class CashFlowForecaster:
    def __init__(self, business_id: str, horizon_days: int = 30):
        self.business_id = business_id
        self.horizon_days = horizon_days
        self.quantiles = [0.10, 0.50, 0.90]
        self.inflow_models: Dict[float, Any] = {}
        self.outflow_models: Dict[float, Any] = {}
        self.invoice_delay_model = InvoiceDelayModel()
        self.feature_cols = [
            "day_of_week", "day_of_month", "month",
            "is_weekend", "is_salary_week", "is_gst_cycle",
            "is_month_start", "is_month_end",
            "sin_day_of_week", "cos_day_of_week",
            "sin_month", "cos_month",
            "days_to_festival", "is_festival_active", "festival_multiplier"
        ]

    def _train_lgbm_quantiles(self, X: pd.DataFrame, y: np.ndarray) -> Dict[float, Any]:
        models = {}
        # Ensure positive target values
        y_clean = np.maximum(y, 0.0)
        for q in self.quantiles:
            model = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=80,
                learning_rate=0.06,
                num_leaves=15,
                min_child_samples=5,
                verbose=-1,
                random_state=42
            )
            model.fit(X, y_clean)
            models[q] = model
        return models

    def fit_and_forecast(
        self,
        business: dict,
        historical_transactions: List[dict],
        recurring_payments: List[dict],
        historical_invoices: List[dict],
        open_invoices: List[dict],
        customers: List[dict],
        forecast_start_date: Optional[date] = None,
        current_balance: Optional[float] = None
    ) -> Dict[str, Any]:
        category = business.get("category", "kirana")
        threshold = float(business.get("min_cash_threshold", 25000.0))

        # Determine dates
        if historical_transactions:
            tx_dates = [t["date"] for t in historical_transactions]
            last_hist_date = max(tx_dates)
            first_hist_date = min(tx_dates)
        else:
            last_hist_date = date(2026, 10, 31)
            first_hist_date = date(2025, 11, 1)

        if forecast_start_date is None:
            forecast_start_date = last_hist_date + timedelta(days=1)

        forecast_dates = [forecast_start_date + timedelta(days=i) for i in range(self.horizon_days)]

        # Determine starting balance
        if current_balance is None:
            if historical_transactions:
                banked_sorted = sorted([t for t in historical_transactions if t.get("is_banked", True)], key=lambda x: (x["date"], x["id"]))
                start_bal = banked_sorted[-1]["balance_after"] if banked_sorted else float(business.get("initial_balance", 50000.0))
            else:
                start_bal = float(business.get("initial_balance", 50000.0))
        else:
            start_bal = float(current_balance)

        # 1. Fit Invoice Delay Model
        self.invoice_delay_model.fit(historical_invoices, customers)
        invoice_inflow_projections = self.invoice_delay_model.get_daily_inflows_from_open_invoices(
            open_invoices, customers, forecast_dates
        )

        # 2. Build Daily Historical Timeseries
        # We split out recurring outflows from variable outflows so ML focuses on variable cash flow
        recurring_categories = {"salary", "rent", "emi", "gst", "vat", "paye_ni"}
        var_txs = []
        for t in historical_transactions:
            t_copy = dict(t)
            # If it's a scheduled recurring expense, don't let ML predict it
            if t.get("category") in recurring_categories:
                continue
            # If it's invoice collection, we exclude it from direct sales ML since invoice model handles it
            if t.get("category") == "invoice_collection":
                continue
            var_txs.append(t_copy)

        ts_df = build_daily_timeseries_df(var_txs, first_hist_date, last_hist_date, category)

        # Fit Inflow and Outflow Quantile Models
        X_train = ts_df[self.feature_cols]
        y_inflow = ts_df["inflow"].values
        y_outflow = ts_df["outflow"].values

        self.inflow_models = self._train_lgbm_quantiles(X_train, y_inflow)
        self.outflow_models = self._train_lgbm_quantiles(X_train, y_outflow)

        # 3. Generate ML Predictions on Forecast Dates
        future_features_df = build_calendar_features_df(forecast_dates, category)
        X_future = future_features_df[self.feature_cols]

        var_inflow_p10 = np.maximum(self.inflow_models[0.10].predict(X_future), 0.0)
        var_inflow_p50 = np.maximum(self.inflow_models[0.50].predict(X_future), 0.0)
        var_inflow_p90 = np.maximum(self.inflow_models[0.90].predict(X_future), 0.0)

        var_outflow_p10 = np.maximum(self.outflow_models[0.10].predict(X_future), 0.0)
        var_outflow_p50 = np.maximum(self.outflow_models[0.50].predict(X_future), 0.0)
        var_outflow_p90 = np.maximum(self.outflow_models[0.90].predict(X_future), 0.0)

        # 4. Add Scheduled Recurring Payments & Invoice Inflows
        # Map recurring outflows by day of month
        recurring_by_day = {}
        for r in recurring_payments:
            if r.get("is_active", True):
                dom = r.get("day_of_month")
                recurring_by_day[dom] = recurring_by_day.get(dom, 0.0) + float(r.get("amount", 0.0))

        # 5. Compute Naive Baseline (4-week rolling same-weekday average from historical ts_df)
        naive_inflow = []
        naive_outflow = []
        for dt in forecast_dates:
            target_dow = dt.weekday()
            # past days matching this weekday
            past_same_dow = ts_df[ts_df["day_of_week"] == target_dow].tail(4)
            if not past_same_dow.empty:
                base_in = float(past_same_dow["inflow"].mean())
                base_out = float(past_same_dow["outflow"].mean())
            else:
                base_in = float(ts_df["inflow"].mean()) if not ts_df.empty else 10000.0
                base_out = float(ts_df["outflow"].mean()) if not ts_df.empty else 8000.0

            # Add recurring outflows
            rec_amt = recurring_by_day.get(dt.day, 0.0)
            naive_outflow.append(base_out + rec_amt)
            # Add invoice p50
            inv_amt = invoice_inflow_projections["p50"].get(dt, 0.0)
            naive_inflow.append(base_in + inv_amt)

        # 6. Aggregate Daily Forecasts & Closing Balances
        daily_forecasts = []
        danger_days = []

        bal_p10 = start_bal
        bal_p50 = start_bal
        bal_p90 = start_bal
        bal_naive = start_bal

        for i, dt in enumerate(forecast_dates):
            rec_amt = recurring_by_day.get(dt.day, 0.0)

            # Inflow for day
            tot_inflow_p10 = var_inflow_p10[i] + invoice_inflow_projections["p10"].get(dt, 0.0)
            tot_inflow_p50 = var_inflow_p50[i] + invoice_inflow_projections["p50"].get(dt, 0.0)
            tot_inflow_p90 = var_inflow_p90[i] + invoice_inflow_projections["p90"].get(dt, 0.0)

            # Ensure quantile ordering: p10 <= p50 <= p90
            tot_inflow_p10 = min(tot_inflow_p10, tot_inflow_p50)
            tot_inflow_p90 = max(tot_inflow_p90, tot_inflow_p50)

            # Outflow for day
            tot_outflow_p10 = var_outflow_p10[i] + rec_amt
            tot_outflow_p50 = var_outflow_p50[i] + rec_amt
            tot_outflow_p90 = var_outflow_p90[i] + rec_amt

            tot_outflow_p10 = min(tot_outflow_p10, tot_outflow_p50)
            tot_outflow_p90 = max(tot_outflow_p90, tot_outflow_p50)

            # Update Balances
            # p50 expected
            bal_p50 = bal_p50 + tot_inflow_p50 - tot_outflow_p50
            # p10 conservative cash lower bound (low inflows, high outflows)
            bal_p10 = bal_p10 + tot_inflow_p10 - tot_outflow_p90
            # p90 optimistic cash upper bound (high inflows, low outflows)
            bal_p90 = bal_p90 + tot_inflow_p90 - tot_outflow_p10

            # Ensure confidence band order
            bal_p10 = min(bal_p10, bal_p50)
            bal_p90 = max(bal_p90, bal_p50)

            # Naive baseline balance
            bal_naive = bal_naive + naive_inflow[i] - naive_outflow[i]

            # Danger Day detection
            is_danger = False
            risk_level = "safe" # safe, warning, critical
            shortfall = 0.0

            if bal_p50 < threshold or bal_p10 < 0:
                is_danger = True
                if bal_p10 < 0 or bal_p50 < 0:
                    risk_level = "critical"
                    shortfall = threshold - bal_p50
                else:
                    risk_level = "warning"
                    shortfall = threshold - bal_p50

            day_dict = {
                "date": dt.isoformat(),
                "day_number": i + 1,
                "inflow_p10": round(tot_inflow_p10, 2),
                "inflow_p50": round(tot_inflow_p50, 2),
                "inflow_p90": round(tot_inflow_p90, 2),
                "outflow_p10": round(tot_outflow_p10, 2),
                "outflow_p50": round(tot_outflow_p50, 2),
                "outflow_p90": round(tot_outflow_p90, 2),
                "balance_p10": round(bal_p10, 2),
                "balance_p50": round(bal_p50, 2),
                "balance_p90": round(bal_p90, 2),
                "naive_balance": round(bal_naive, 2),
                "min_cash_threshold": threshold,
                "is_danger": is_danger,
                "risk_level": risk_level,
                "shortfall": round(max(0.0, shortfall), 2),
                "recurring_outflow": round(rec_amt, 2),
                "invoice_inflow": round(invoice_inflow_projections["p50"].get(dt, 0.0), 2)
            }
            daily_forecasts.append(day_dict)

            if is_danger:
                danger_days.append({
                    "date": dt.isoformat(),
                    "day_number": i + 1,
                    "risk_level": risk_level,
                    "balance_p50": round(bal_p50, 2),
                    "balance_p10": round(bal_p10, 2),
                    "shortfall": round(max(0.0, shortfall), 2),
                    "recurring_outflow": round(rec_amt, 2),
                })

        min_bal_p50 = min(d["balance_p50"] for d in daily_forecasts)
        min_bal_p10 = min(d["balance_p10"] for d in daily_forecasts)
        max_shortfall = max(d["shortfall"] for d in daily_forecasts)

        # Primary crunch driver diagnosis
        primary_driver = "Stable cash flow"
        if danger_days:
            has_gst_driver = any(d["recurring_outflow"] > 0 and date.fromisoformat(d["date"]).day == 20 for d in danger_days)
            has_salary_driver = any(d["recurring_outflow"] > 0 and date.fromisoformat(d["date"]).day == 5 for d in danger_days)
            if has_gst_driver:
                primary_driver = "GST 3B tax liability on 20th combined with customer collection delays"
            elif has_salary_driver:
                primary_driver = "Monthly payroll disbursement on 5th exceeding available working capital buffer"
            else:
                primary_driver = "Sustained revenue slowdown and cumulative supplier outflows"

        return {
            "business_id": self.business_id,
            "forecast_start_date": forecast_start_date.isoformat(),
            "forecast_end_date": forecast_dates[-1].isoformat(),
            "horizon_days": self.horizon_days,
            "initial_balance": round(start_bal, 2),
            "min_cash_threshold": threshold,
            "min_projected_balance_p50": round(min_bal_p50, 2),
            "min_projected_balance_p10": round(min_bal_p10, 2),
            "max_shortfall": round(max_shortfall, 2),
            "danger_days_count": len(danger_days),
            "first_danger_date": danger_days[0]["date"] if danger_days else None,
            "primary_driver": primary_driver,
            "daily_forecasts": daily_forecasts,
            "danger_days": danger_days
        }
