# CashLoop Walk-Forward Backtesting Report

**Evaluation Window**: 2026-10-01 to 2026-10-30 (30-day forward horizon)

**Sample Size**: 4 Indian MSMEs

## Overall Forecast Performance

| Metric | LightGBM + Invoice Model | Naive 4-Week Baseline | Relative Gain |
| :--- | :--- | :--- | :--- |
| **WAPE** | **0.0478 (4.8%)** | 0.0791 (7.9%) | **+39.6% error reduction** |
| **MAPE** | **4.76%** | 7.49% | **+36.4% error reduction** |
| **80% Prediction Interval Coverage** | **96.7%** | N/A | Target: 80.0% |

## Per-Business Breakdown

| Business ID | Business Name | Category | LGBM WAPE | Naive WAPE | Error Reduction | [p10, p90] Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `biz_001` | Sharma Provision & Kirana Store | `kirana` | 0.047 | 0.185 | **74.6%** | 100.0% |
| `biz_002` | Om Sai Super Mart | `kirana` | 0.050 | 0.074 | **32.8%** | 100.0% |
| `biz_003` | Gupta Daily Needs | `kirana` | 0.034 | 0.018 | **-88.3%** | 100.0% |
| `biz_004` | Mahalaxmi Grocery Hub | `kirana` | 0.061 | 0.040 | **-53.3%** | 86.7% |
