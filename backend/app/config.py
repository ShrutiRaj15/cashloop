"""CashLoop UK SME Market Configuration and Tax Calendar.

Central configuration defining market currency, locale, terminology,
and statutory tax payment schedules for United Kingdom Small and Medium Enterprises (SMEs).
"""

from typing import Dict, Any

MARKET_COUNTRY = "GB"
MARKET_LOCALE = "en-GB"
MARKET_CURRENCY = "GBP"
MARKET_CURRENCY_SYMBOL = "£"

# Terminology mappings for UK SME market
TERMINOLOGY = {
    "business_label": "SME",
    "business_id_label": "Companies House Number",
    "tax_id_label": "VAT Number",
    "lender_label": "Lender / Commercial Credit Provider",
    "payment_rails": ["Faster Payments", "BACS", "CHAPS", "Direct Debit", "Open Banking"],
    "financing_rails": ["Invoice Finance", "Revolving Credit Line", "Working Capital Facility"],
}

# Statutory UK Tax Calendar definitions
# Sources: HMRC official guidelines (gov.uk)
# DISCLAIMER: Verify before production against individual company accounting periods and HMRC notices.
UK_TAX_CALENDAR: Dict[str, Dict[str, Any]] = {
    "VAT": {
        "title": "Value Added Tax (VAT) Return & Payment",
        "frequency": "quarterly",
        "due_rule": "1 calendar month + 7 days after VAT accounting quarter ends",
        "standard_due_day": 7, # 7th of the month following quarter + 1 month
        "statutory_source": "https://www.gov.uk/vat-returns",
        "notes": "Verify before production: companies may be on staggered VAT quarters (March/June/Sept/Dec, Jan/April/July/Oct, or Feb/May/Aug/Nov) or the Annual Accounting Scheme.",
    },
    "PAYE_NI": {
        "title": "PAYE & Class 1 National Insurance",
        "frequency": "monthly",
        "due_rule": "22nd of each month for electronic payment (19th if by post)",
        "standard_due_day": 22,
        "statutory_source": "https://www.gov.uk/paye-for-employers/paying-hmrc",
        "notes": "Verify before production: applies to monthly payroll RTI submissions.",
    },
    "CORPORATION_TAX": {
        "title": "Corporation Tax",
        "frequency": "annual",
        "due_rule": "9 months and 1 day after the end of your company accounting period",
        "statutory_source": "https://www.gov.uk/corporation-tax",
        "notes": "Verify before production: for profits up to £1.5m, payment deadline is 9 months and 1 day after accounting period end.",
    },
}
