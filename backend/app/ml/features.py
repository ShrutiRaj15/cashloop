import math
from datetime import date, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from app.data.generator import FESTIVALS

def get_festival_features(dt: date, category: str = "corner_shop") -> Dict[str, float]:
    min_dist = 999
    is_active = 0.0
    mult = 1.0

    col_map = {
        "corner_shop": "multiplier_corner",
        "cafe": "multiplier_cafe",
        "takeaway_restaurant": "multiplier_restaurant",
        "tradesperson_builder": "multiplier_trades",
        "ecommerce_seller": "multiplier_ecommerce",
        "small_manufacturer": "multiplier_mfg",
        "wholesaler": "multiplier_wholesaler",
        # Legacy aliases
        "kirana": "multiplier_corner",
        "sweet_shop": "multiplier_cafe",
        "garment_wholesaler": "multiplier_wholesaler",
    }
    mult_col = col_map.get(category, "multiplier_corner")

    for fest in FESTIVALS:
        diff = (dt - fest["date"]).days
        if abs(diff) < abs(min_dist):
            min_dist = diff

        if -fest["window_before"] <= diff <= fest["window_after"]:
            is_active = 1.0
            peak_factor = 1.0 - (abs(diff) / (fest["window_before"] + fest["window_after"] + 1)) * 0.4
            mult = max(mult, 1.0 + (fest.get(mult_col, 1.2) - 1.0) * peak_factor)

    return {
        "days_to_festival": float(min_dist),
        "is_festival_active": is_active,
        "festival_multiplier": mult,
    }

def build_calendar_features_df(dates: List[date], category: str = "corner_shop") -> pd.DataFrame:
    rows = []
    for dt in dates:
        day_of_week = dt.weekday()
        day_of_month = dt.day
        month = dt.month

        fest_feats = get_festival_features(dt, category)

        # UK Tax and statutory payment cycles:
        # VAT quarterly due 7th (Feb, May, Aug, Nov) or PAYE due 22nd
        is_tax_cycle = 1.0 if ((1 <= day_of_month <= 8 and month in [2, 5, 8, 11]) or (18 <= day_of_month <= 23)) else 0.0

        row = {
            "date": dt,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "month": month,
            "is_weekend": 1.0 if day_of_week in [5, 6] else 0.0,
            "is_salary_week": 1.0 if 24 <= day_of_month <= 31 else 0.0,
            "is_gst_cycle": is_tax_cycle, # VAT / PAYE statutory tax cycle (retaining column name for feature matrix compatibility)
            "is_vat_cycle": is_tax_cycle,
            "is_month_start": 1.0 if day_of_month <= 5 else 0.0,
            "is_month_end": 1.0 if day_of_month >= 25 else 0.0,
            "sin_day_of_week": math.sin(2 * math.pi * day_of_week / 7),
            "cos_day_of_week": math.cos(2 * math.pi * day_of_week / 7),
            "sin_month": math.sin(2 * math.pi * (month - 1) / 12),
            "cos_month": math.cos(2 * math.pi * (month - 1) / 12),
            **fest_feats
        }
        rows.append(row)

    return pd.DataFrame(rows)

def build_daily_timeseries_df(transactions: List[dict], start_date: date, end_date: date, category: str = "kirana") -> pd.DataFrame:
    # Build complete date index
    curr = start_date
    all_dates = []
    while curr <= end_date:
        all_dates.append(curr)
        curr += timedelta(days=1)

    cal_df = build_calendar_features_df(all_dates, category)

    # Aggregate transactions by date and type
    tx_df = pd.DataFrame(transactions)
    if tx_df.empty:
        cal_df["inflow"] = 0.0
        cal_df["outflow"] = 0.0
        cal_df["net"] = 0.0
        return cal_df

    # Filter to banked transactions only (cash in bank)
    banked_tx = tx_df[tx_df["is_banked"] == True].copy()
    if banked_tx.empty:
        cal_df["inflow"] = 0.0
        cal_df["outflow"] = 0.0
        cal_df["net"] = 0.0
        return cal_df

    # Group by date and type
    pivot = banked_tx.groupby(["date", "type"])["amount"].sum().unstack(fill_value=0.0).reset_index()
    if "inflow" not in pivot.columns:
        pivot["inflow"] = 0.0
    if "outflow" not in pivot.columns:
        pivot["outflow"] = 0.0

    merged = pd.merge(cal_df, pivot, on="date", how="left").fillna(0.0)
    merged["net"] = merged["inflow"] - merged["outflow"]

    # Compute rolling and lag features
    for col in ["inflow", "outflow"]:
        merged[f"{col}_lag_1"] = merged[col].shift(1).bfill()
        merged[f"{col}_lag_7"] = merged[col].shift(7).bfill()
        merged[f"{col}_lag_14"] = merged[col].shift(14).bfill()
        merged[f"{col}_rolling_mean_7"] = merged[col].shift(1).rolling(7, min_periods=1).mean().bfill()
        merged[f"{col}_rolling_std_7"] = merged[col].shift(1).rolling(7, min_periods=1).std().fillna(0.0)
        merged[f"{col}_rolling_mean_28"] = merged[col].shift(1).rolling(28, min_periods=1).mean().bfill()

    return merged
