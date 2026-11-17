import os
import sys
import json
from datetime import date, timedelta
from typing import Dict, List, Any
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.models.database import SessionLocal
from app.models.schema import Business, Transaction, RecurringPayment, Invoice, Customer
from app.ml.forecaster import CashFlowForecaster

def calculate_wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    sum_actual = np.sum(np.abs(actual))
    if sum_actual == 0:
        return 0.0
    return float(np.sum(np.abs(actual - predicted)) / sum_actual)

def calculate_mape(actual: np.ndarray, predicted: np.ndarray, eps: float = 1e-4) -> float:
    denom = np.maximum(np.abs(actual), eps)
    return float(np.mean(np.abs((actual - predicted) / denom))) * 100.0

def run_backtest(
    cutoff_date: date = date(2026, 10, 1),
    horizon_days: int = 30,
    max_businesses: int = 12
) -> Dict[str, Any]:
    db = SessionLocal()
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    try:
        businesses = db.query(Business).limit(max_businesses).all()
        eval_start = cutoff_date
        eval_end = cutoff_date + timedelta(days=horizon_days - 1)

        business_results = []
        lgbm_wapes = []
        naive_wapes = []
        lgbm_mapes = []
        naive_mapes = []
        interval_coverages = []

        print(f"Running walk-forward backtest across {len(businesses)} MSMEs...")
        print(f"Training cutoff: {cutoff_date} | Forecast Horizon: {eval_start} to {eval_end} ({horizon_days} days)")

        for biz in businesses:
            biz_id = biz.id
            biz_dict = {
                "id": biz.id,
                "name": biz.name,
                "category": biz.category,
                "initial_balance": biz.initial_balance,
                "min_cash_threshold": biz.min_cash_threshold
            }

            # Fetch historical training transactions up to cutoff_date
            train_txs = (
                db.query(Transaction)
                .filter(Transaction.business_id == biz_id, Transaction.date < cutoff_date)
                .all()
            )
            train_tx_dicts = [
                {
                    "id": t.id,
                    "date": t.date,
                    "type": t.type,
                    "category": t.category,
                    "amount": t.amount,
                    "is_banked": t.is_banked,
                    "balance_after": t.balance_after
                }
                for t in train_txs
            ]

            # Fetch recurring payments
            recurring = (
                db.query(RecurringPayment)
                .filter(RecurringPayment.business_id == biz_id)
                .all()
            )
            rec_dicts = [
                {
                    "id": r.id,
                    "title": r.title,
                    "category": r.category,
                    "amount": r.amount,
                    "day_of_month": r.day_of_month,
                    "is_active": r.is_active
                }
                for r in recurring
            ]

            # Fetch invoices
            hist_invoices = (
                db.query(Invoice)
                .filter(Invoice.business_id == biz_id, Invoice.issue_date < cutoff_date)
                .all()
            )
            hist_inv_dicts = [
                {
                    "id": inv.id,
                    "customer_id": inv.customer_id,
                    "invoice_number": inv.invoice_number,
                    "amount": inv.amount,
                    "issue_date": inv.issue_date,
                    "due_date": inv.due_date,
                    "paid_date": inv.paid_date,
                    "actual_delay_days": inv.actual_delay_days
                }
                for inv in hist_invoices
            ]

            open_invoices = [inv for inv in hist_inv_dicts if inv["paid_date"] >= cutoff_date]

            # Fetch customers
            custs = db.query(Customer).filter(Customer.business_id == biz_id).all()
            cust_dicts = [
                {
                    "id": c.id,
                    "name": c.name,
                    "payment_habit": c.payment_habit,
                    "avg_delay_days": c.avg_delay_days,
                    "delay_std_days": c.delay_std_days
                }
                for c in custs
            ]

            # Starting balance at cutoff
            sorted_banked = sorted([t for t in train_tx_dicts if t["is_banked"]], key=lambda x: (x["date"], x["id"]))
            start_bal = sorted_banked[-1]["balance_after"] if sorted_banked else biz.initial_balance

            # Ground truth actuals during eval window
            actual_txs = (
                db.query(Transaction)
                .filter(
                    Transaction.business_id == biz_id,
                    Transaction.date >= eval_start,
                    Transaction.date <= eval_end,
                    Transaction.is_banked == True
                )
                .order_by(Transaction.date.asc(), Transaction.id.asc())
                .all()
            )

            # Build daily ground truth balance series
            actual_daily_bal = {}
            running_b = start_bal
            tx_by_date = {}
            for t in actual_txs:
                tx_by_date.setdefault(t.date, []).append(t)

            cur_d = eval_start
            actual_dates = []
            actual_balances = []
            while cur_d <= eval_end:
                for t in tx_by_date.get(cur_d, []):
                    if t.type == "inflow":
                        running_b += t.amount
                    else:
                        running_b -= t.amount
                actual_daily_bal[cur_d] = running_b
                actual_dates.append(cur_d)
                actual_balances.append(running_b)
                cur_d += timedelta(days=1)

            actual_balances = np.array(actual_balances)

            # Run forecaster
            forecaster = CashFlowForecaster(business_id=biz_id, horizon_days=horizon_days)
            forecast_out = forecaster.fit_and_forecast(
                business=biz_dict,
                historical_transactions=train_tx_dicts,
                recurring_payments=rec_dicts,
                historical_invoices=hist_inv_dicts,
                open_invoices=open_invoices,
                customers=cust_dicts,
                forecast_start_date=eval_start,
                current_balance=start_bal
            )

            daily_preds = forecast_out["daily_forecasts"]
            pred_p50 = np.array([d["balance_p50"] for d in daily_preds])
            pred_p10 = np.array([d["balance_p10"] for d in daily_preds])
            pred_p90 = np.array([d["balance_p90"] for d in daily_preds])
            pred_naive = np.array([d["naive_balance"] for d in daily_preds])

            # Evaluate Metrics
            wape_lgbm = calculate_wape(actual_balances, pred_p50)
            wape_naive = calculate_wape(actual_balances, pred_naive)
            mape_lgbm = calculate_mape(actual_balances, pred_p50)
            mape_naive = calculate_mape(actual_balances, pred_naive)

            # 80% Confidence Interval Coverage: actual within [p10, p90]
            inside_interval = (actual_balances >= pred_p10) & (actual_balances <= pred_p90)
            coverage = float(np.mean(inside_interval)) * 100.0

            lgbm_wapes.append(wape_lgbm)
            naive_wapes.append(wape_naive)
            lgbm_mapes.append(mape_lgbm)
            naive_mapes.append(mape_naive)
            interval_coverages.append(coverage)

            biz_summary = {
                "business_id": biz.id,
                "name": biz.name,
                "category": biz.category,
                "wape_lgbm": round(wape_lgbm, 4),
                "wape_naive": round(wape_naive, 4),
                "wape_improvement_pct": round(((wape_naive - wape_lgbm) / max(wape_naive, 1e-4)) * 100.0, 1),
                "mape_lgbm": round(mape_lgbm, 2),
                "mape_naive": round(mape_naive, 2),
                "interval_coverage_pct": round(coverage, 1),
                "danger_days_predicted": forecast_out["danger_days_count"]
            }
            business_results.append(biz_summary)

        # Aggregate metrics
        avg_lgbm_wape = float(np.mean(lgbm_wapes))
        avg_naive_wape = float(np.mean(naive_wapes))
        avg_lgbm_mape = float(np.mean(lgbm_mapes))
        avg_naive_mape = float(np.mean(naive_mapes))
        avg_coverage = float(np.mean(interval_coverages))
        overall_improvement = float((avg_naive_wape - avg_lgbm_wape) / avg_naive_wape * 100.0)

        report = {
            "evaluation_period": f"{eval_start} to {eval_end}",
            "horizon_days": horizon_days,
            "businesses_evaluated": len(businesses),
            "metrics": {
                "lgbm_wape_avg": round(avg_lgbm_wape, 4),
                "naive_wape_avg": round(avg_naive_wape, 4),
                "wape_improvement_pct": round(overall_improvement, 1),
                "lgbm_mape_avg_pct": round(avg_lgbm_mape, 2),
                "naive_mape_avg_pct": round(avg_naive_mape, 2),
                "p10_p90_interval_coverage_pct": round(avg_coverage, 1)
            },
            "per_business_results": business_results
        }

        # Save JSON report
        json_path = os.path.join(reports_dir, "backtest_metrics.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # Save Markdown report
        md_path = os.path.join(reports_dir, "backtest_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# CashLoop Walk-Forward Backtesting Report\n\n")
            f.write(f"**Evaluation Window**: {eval_start} to {eval_end} (30-day forward horizon)\n\n")
            f.write(f"**Sample Size**: {len(businesses)} Indian MSMEs\n\n")
            f.write("## Overall Forecast Performance\n\n")
            f.write("| Metric | LightGBM + Invoice Model | Naive 4-Week Baseline | Relative Gain |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            f.write(f"| **WAPE** | **{avg_lgbm_wape:.4f} ({avg_lgbm_wape*100:.1f}%)** | {avg_naive_wape:.4f} ({avg_naive_wape*100:.1f}%) | **+{overall_improvement:.1f}% error reduction** |\n")
            f.write(f"| **MAPE** | **{avg_lgbm_mape:.2f}%** | {avg_naive_mape:.2f}% | **+{((avg_naive_mape - avg_lgbm_mape)/avg_naive_mape)*100:.1f}% error reduction** |\n")
            f.write(f"| **80% Prediction Interval Coverage** | **{avg_coverage:.1f}%** | N/A | Target: 80.0% |\n\n")
            f.write("## Per-Business Breakdown\n\n")
            f.write("| Business ID | Business Name | Category | LGBM WAPE | Naive WAPE | Error Reduction | [p10, p90] Coverage |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for r in business_results:
                f.write(f"| `{r['business_id']}` | {r['name']} | `{r['category']}` | {r['wape_lgbm']:.3f} | {r['wape_naive']:.3f} | **{r['wape_improvement_pct']}%** | {r['interval_coverage_pct']}% |\n")

        print("\n" + "="*60)
        print("CASHLOOP WALK-FORWARD BACKTEST RESULTS")
        print("="*60)
        print(f"LightGBM Average WAPE:     {avg_lgbm_wape:.4f} ({avg_lgbm_wape*100:.1f}%)")
        print(f"Naive Baseline WAPE:       {avg_naive_wape:.4f} ({avg_naive_wape*100:.1f}%)")
        print(f"WAPE Error Reduction:      +{overall_improvement:.1f}% vs baseline")
        print(f"LightGBM Average MAPE:     {avg_lgbm_mape:.2f}%")
        print(f"Naive Baseline MAPE:       {avg_naive_mape:.2f}%")
        print(f"Empirical Coverage [p10,p90]: {avg_coverage:.1f}% (Target: ~80%)")
        print(f"Report saved to: {md_path}")
        print("="*60 + "\n")

        return report

    finally:
        db.close()

if __name__ == "__main__":
    run_backtest()
