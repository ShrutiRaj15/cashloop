import random
import uuid
from datetime import date, timedelta
from typing import Dict, List, Tuple

# UK Calendar Events & Seasonal Peaks in our simulation year (Nov 1, 2025 to Nov 30, 2026)
# Each event has a peak date and a window of days around it with sector multipliers
UK_CALENDAR_EVENTS = [
    {
        "name": "Black Friday / Cyber Monday 2025",
        "date": date(2025, 11, 28),
        "window_before": 3,
        "window_after": 3,
        "multiplier_corner": 1.3,
        "multiplier_cafe": 1.2,
        "multiplier_restaurant": 1.3,
        "multiplier_trades": 0.9,
        "multiplier_ecommerce": 3.2,
        "multiplier_mfg": 1.2,
        "multiplier_wholesaler": 2.2,
    },
    {
        "name": "Christmas & New Year Shopping Rush 2025",
        "date": date(2025, 12, 23),
        "window_before": 10,
        "window_after": 2,
        "multiplier_corner": 1.9,
        "multiplier_cafe": 1.5,
        "multiplier_restaurant": 1.8,
        "multiplier_trades": 0.7,
        "multiplier_ecommerce": 2.6,
        "multiplier_mfg": 1.1,
        "multiplier_wholesaler": 2.0,
    },
    {
        "name": "Easter Holiday Weekend 2026",
        "date": date(2026, 4, 5),
        "window_before": 4,
        "window_after": 2,
        "multiplier_corner": 1.5,
        "multiplier_cafe": 2.1,
        "multiplier_restaurant": 2.0,
        "multiplier_trades": 1.2,
        "multiplier_ecommerce": 1.3,
        "multiplier_mfg": 1.1,
        "multiplier_wholesaler": 1.4,
    },
    {
        "name": "Early May Bank Holiday 2026",
        "date": date(2026, 5, 4),
        "window_before": 2,
        "window_after": 1,
        "multiplier_corner": 1.4,
        "multiplier_cafe": 1.9,
        "multiplier_restaurant": 1.8,
        "multiplier_trades": 1.1,
        "multiplier_ecommerce": 1.2,
        "multiplier_mfg": 1.0,
        "multiplier_wholesaler": 1.3,
    },
    {
        "name": "Spring Bank Holiday 2026",
        "date": date(2026, 5, 25),
        "window_before": 2,
        "window_after": 1,
        "multiplier_corner": 1.4,
        "multiplier_cafe": 2.0,
        "multiplier_restaurant": 1.9,
        "multiplier_trades": 1.2,
        "multiplier_ecommerce": 1.2,
        "multiplier_mfg": 1.0,
        "multiplier_wholesaler": 1.3,
    },
    {
        "name": "Summer School Holidays Peak 2026",
        "date": date(2026, 8, 8),
        "window_before": 14,
        "window_after": 14,
        "multiplier_corner": 1.5,
        "multiplier_cafe": 1.8,
        "multiplier_restaurant": 1.7,
        "multiplier_trades": 1.4,
        "multiplier_ecommerce": 1.1,
        "multiplier_mfg": 0.9,
        "multiplier_wholesaler": 1.2,
    },
    {
        "name": "Summer Bank Holiday 2026",
        "date": date(2026, 8, 31),
        "window_before": 2,
        "window_after": 1,
        "multiplier_corner": 1.4,
        "multiplier_cafe": 1.9,
        "multiplier_restaurant": 1.8,
        "multiplier_trades": 1.1,
        "multiplier_ecommerce": 1.2,
        "multiplier_mfg": 1.0,
        "multiplier_wholesaler": 1.3,
    },
    {
        "name": "Black Friday 2026",
        "date": date(2026, 11, 27),
        "window_before": 3,
        "window_after": 3,
        "multiplier_corner": 1.3,
        "multiplier_cafe": 1.2,
        "multiplier_restaurant": 1.3,
        "multiplier_trades": 0.9,
        "multiplier_ecommerce": 3.3,
        "multiplier_mfg": 1.2,
        "multiplier_wholesaler": 2.3,
    },
]

# Backward compatibility alias
FESTIVALS = UK_CALENDAR_EVENTS

UK_CITIES = [
    ("London", "Greater London"),
    ("Manchester", "Greater Manchester"),
    ("Birmingham", "West Midlands"),
    ("Leeds", "West Yorkshire"),
    ("Bristol", "City of Bristol"),
    ("Edinburgh", "Midlothian"),
    ("Glasgow", "Lanarkshire"),
    ("Liverpool", "Merseyside"),
    ("Sheffield", "South Yorkshire"),
    ("Newcastle upon Tyne", "Tyne and Wear"),
    ("Nottingham", "Nottinghamshire"),
    ("Southampton", "Hampshire"),
]

# 30 UK SMEs across 7 business types with realistic daily revenues (£480 - £2,200) and healthy opening balances (£20k - £85k)
BUSINESS_TEMPLATES = [
    # 1-5: Corner Shops (B2C heavy, daily card / cash, fast inventory turn)
    {"name": "High Street News & Convenience", "category": "corner_shop", "daily_base": 550, "unbanked_share": 0.15, "threshold": 4500, "init_bal": 24000},
    {"name": "Piccadilly Corner Express", "category": "corner_shop", "daily_base": 720, "unbanked_share": 0.12, "threshold": 5500, "init_bal": 28000},
    {"name": "Borough Green Local Grocer", "category": "corner_shop", "daily_base": 480, "unbanked_share": 0.18, "threshold": 4000, "init_bal": 20000},
    {"name": "Regent Street Food & Wine", "category": "corner_shop", "daily_base": 850, "unbanked_share": 0.10, "threshold": 6500, "init_bal": 32000},
    {"name": "St Giles Corner Store", "category": "corner_shop", "daily_base": 520, "unbanked_share": 0.14, "threshold": 4200, "init_bal": 22000},

    # 6-10: Cafes (Card payments, strong weekend surges, seasonal weather peaks)
    {"name": "The Daily Grind Espresso Bar", "category": "cafe", "daily_base": 650, "unbanked_share": 0.08, "threshold": 5000, "init_bal": 25000},
    {"name": "Northern Quarter Artisan Coffee", "category": "cafe", "daily_base": 780, "unbanked_share": 0.05, "threshold": 6000, "init_bal": 30000},
    {"name": "Clifton Village Bakehouse & Tea", "category": "cafe", "daily_base": 580, "unbanked_share": 0.10, "threshold": 4500, "init_bal": 22000},
    {"name": "Royal Mile Roasters & Cafe", "category": "cafe", "daily_base": 820, "unbanked_share": 0.06, "threshold": 6200, "init_bal": 34000},
    {"name": "Canal Basin Cafe & Kitchen", "category": "cafe", "daily_base": 610, "unbanked_share": 0.08, "threshold": 4800, "init_bal": 24000},

    # 11-14: Takeaway Restaurants (Evenings, weekends, delivery platform payouts)
    {"name": "Albion Fish & Chip Shop", "category": "takeaway_restaurant", "daily_base": 750, "unbanked_share": 0.18, "threshold": 5500, "init_bal": 27000},
    {"name": "Balti Triangle Kitchen", "category": "takeaway_restaurant", "daily_base": 920, "unbanked_share": 0.12, "threshold": 7000, "init_bal": 35000},
    {"name": "Soho Wood-Fired Pizzeria", "category": "takeaway_restaurant", "daily_base": 1100, "unbanked_share": 0.08, "threshold": 8500, "init_bal": 42000},
    {"name": "Brummie Grill & Rotisserie", "category": "takeaway_restaurant", "daily_base": 680, "unbanked_share": 0.15, "threshold": 5200, "init_bal": 26000},

    # 15-18: Tradesperson / Builders (Invoice-based staged milestones, materials procurement, CIS deductions)
    {"name": "Apex Electrical Contractors Ltd", "category": "tradesperson_builder", "daily_base": 1200, "unbanked_share": 0.02, "threshold": 9000, "init_bal": 45000},
    {"name": "Severn Valley Plumbing & Heating Ltd", "category": "tradesperson_builder", "daily_base": 980, "unbanked_share": 0.03, "threshold": 7500, "init_bal": 38000},
    {"name": "Caledonian Roofing & Joinery Ltd", "category": "tradesperson_builder", "daily_base": 1350, "unbanked_share": 0.02, "threshold": 10000, "init_bal": 52000},
    {"name": "Pennine Building & Refurbishment Ltd", "category": "tradesperson_builder", "daily_base": 1150, "unbanked_share": 0.02, "threshold": 8500, "init_bal": 44000},

    # 19-22: E-commerce Sellers (Stripe/Shopify automated payouts, high Q4 holiday peak)
    {"name": "PureVibe Organics & Wellness Ltd", "category": "ecommerce_seller", "daily_base": 1450, "unbanked_share": 0.00, "threshold": 11000, "init_bal": 55000},
    {"name": "UrbanTrend Apparel Online Ltd", "category": "ecommerce_seller", "daily_base": 1650, "unbanked_share": 0.00, "threshold": 12500, "init_bal": 62000},
    {"name": "Nordic Living Homeware Direct Ltd", "category": "ecommerce_seller", "daily_base": 1250, "unbanked_share": 0.00, "threshold": 9500, "init_bal": 48000},
    {"name": "TechGear UK Direct Ltd", "category": "ecommerce_seller", "daily_base": 1850, "unbanked_share": 0.00, "threshold": 14000, "init_bal": 70000},

    # 23-26: Small Manufacturers (Tooling, raw materials, commercial equipment leases, 30-day corporate trade credit)
    {"name": "Thames Valley Precision Machining Ltd", "category": "small_manufacturer", "daily_base": 1900, "unbanked_share": 0.01, "threshold": 15000, "init_bal": 75000},
    {"name": "Midlands Sheet Metal Fabrications Ltd", "category": "small_manufacturer", "daily_base": 1700, "unbanked_share": 0.01, "threshold": 13500, "init_bal": 68000},
    {"name": "Tyne Packaging & Corrugated Works Ltd", "category": "small_manufacturer", "daily_base": 1500, "unbanked_share": 0.02, "threshold": 12000, "init_bal": 60000},
    {"name": "Clydebank Hydraulics & Valves Ltd", "category": "small_manufacturer", "daily_base": 2100, "unbanked_share": 0.01, "threshold": 16500, "init_bal": 82000},

    # 27-30: Wholesalers (High volume B2B pallet orders, 30-60 day trade terms, warehouse logistics)
    {"name": "Great British Catering Supplies Ltd", "category": "wholesaler", "daily_base": 2200, "unbanked_share": 0.02, "threshold": 17000, "init_bal": 85000},
    {"name": "Mersey Drinks & Beverage Wholesalers Ltd", "category": "wholesaler", "daily_base": 1950, "unbanked_share": 0.03, "threshold": 15500, "init_bal": 78000},
    {"name": "Wessex Hardware & Tool Distributors Ltd", "category": "wholesaler", "daily_base": 1600, "unbanked_share": 0.02, "threshold": 12500, "init_bal": 64000},
    {"name": "Highland Foodservice Logistics Ltd", "category": "wholesaler", "daily_base": 1800, "unbanked_share": 0.02, "threshold": 14000, "init_bal": 72000},
]

UK_CUSTOMER_NAMES = [
    "Harrington Retail Group Ltd", "Pendleton & Sons Commercial Ltd", "Cotswold Stores Ltd",
    "Oakridge Trading Co Ltd", "Mayfair Commercial Contracts Ltd", "Waverley Distribution Ltd",
    "Beacon Hill Supplies Ltd", "Sterling Building Solutions Ltd", "Kensington Hospitality Ltd",
    "Mercia Logistics Ltd", "Vanguard Property Services Ltd", "Abbey Forecourts & Retail Ltd",
    "Crown Hotel & Leisure Ltd", "Highland Craft Breweries Ltd", "Brunel Engineering Works Ltd",
    "Pennine Retail Partners Ltd", "Chiltern Fresh Foods Ltd", "Severnside Trading Group Ltd"
]

def generate_vat_number(seed_int: int = 100000000) -> str:
    """Generate valid 9-digit UK VAT registration number prefixed with GB."""
    return f"GB{seed_int:09d}"

def generate_companies_house_number(idx: int) -> str:
    """Generate standard 8-digit UK Companies House registered company number."""
    # UK company numbers are typically 8 numeric digits or 2 letters + 6 digits
    return f"{8412000 + idx + 1:08d}"

class SyntheticDataGenerator:
    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.start_date = date(2025, 11, 1)
        # 12 months history + 30 days future ground truth
        self.end_date = date(2026, 11, 30)
        self.cutoff_date = date(2026, 10, 31) # End of historical training window

    def get_festival_multiplier(self, cur_date: date, category: str) -> float:
        # Category key mapping
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
        mult_key = col_map.get(category, "multiplier_corner")

        for event in UK_CALENDAR_EVENTS:
            diff = (cur_date - event["date"]).days
            if -event["window_before"] <= diff <= event["window_after"]:
                peak_factor = 1.0 - (abs(diff) / (event["window_before"] + event["window_after"] + 1)) * 0.4
                return 1.0 + (event.get(mult_key, 1.2) - 1.0) * peak_factor
        return 1.0

    def generate_all_data(self) -> Dict[str, list]:
        businesses = []
        customers = []
        invoices = []
        recurring_payments = []
        transactions = []

        # Exactly 4 businesses get an injected cash crunch; 4 have drift
        crunch_biz_indices = {2, 9, 16, 24} # 4 crunch businesses (1 corner, 1 cafe, 1 builder, 1 mfg)
        drift_biz_indices = {4, 11, 18, 26}

        for idx, template in enumerate(BUSINESS_TEMPLATES):
            biz_id = generate_companies_house_number(idx)
            city, region = UK_CITIES[idx % len(UK_CITIES)]
            has_crunch = idx in crunch_biz_indices
            has_drift = idx in drift_biz_indices
            vat_num = generate_vat_number(128490000 + idx * 73 + 17)

            biz_record = {
                "id": biz_id,
                "name": template["name"],
                "category": template["category"],
                "city": city,
                "state": region,
                "vat_number": vat_num,
                "gstin": vat_num, # legacy compatibility
                "min_cash_threshold": float(template["threshold"]),
                "initial_balance": float(template["init_bal"]),
                "current_balance": float(template["init_bal"]),
                "unbanked_cash_share": float(template["unbanked_share"]),
                "has_drift": has_drift,
                "has_crunch_injected": has_crunch,
            }

            # 1. Customers for B2B vs Retail
            is_b2b = template["category"] in ["tradesperson_builder", "small_manufacturer", "wholesaler", "ecommerce_seller"]
            num_customers = 8 if is_b2b else 5
            biz_customers = []
            habits_pool = [
                ("disciplined", 1.0, 2.0),
                ("chronic_late", 21.0, 4.0),
                ("erratic", 10.0, 12.0),
                ("seasonal", 5.0, 7.0),
            ]
            for c_idx in range(num_customers):
                c_id = f"cust_{biz_id}_{c_idx+1:02d}"
                c_name = f"{random.choice(UK_CUSTOMER_NAMES)} #{c_idx+1}"
                habit, avg_delay, std_delay = habits_pool[c_idx % len(habits_pool)]
                cust_rec = {
                    "id": c_id,
                    "business_id": biz_id,
                    "name": c_name,
                    "payment_habit": habit,
                    "avg_delay_days": float(avg_delay),
                    "delay_std_days": float(std_delay),
                    "credit_limit": float(random.choice([10000, 25000, 50000, 100000])),
                    "phone": f"+44 79{random.randint(10000000, 99999999)}",
                }
                customers.append(cust_rec)
                biz_customers.append(cust_rec)

            # 2. Recurring Monthly & Quarterly Outflows (UK Statutory & Operating)
            # - Commercial Lease Rent (1st of month)
            # - Staff Payroll (28th of month)
            # - HMRC PAYE & NI (22nd of month)
            # - Term Loan / Equipment Finance (10th of month)
            # - HMRC Quarterly VAT Return & Settlement (7th of Feb, May, Aug, Nov)
            daily_base = template["daily_base"]
            biz_recurring = [
                {
                    "id": f"rec_{biz_id}_rent",
                    "business_id": biz_id,
                    "title": "Commercial Premises Lease Rent",
                    "category": "rent",
                    "amount": round(daily_base * random.uniform(1.8, 2.5), -1),
                    "frequency": "monthly",
                    "day_of_month": 1,
                    "is_active": True,
                },
                {
                    "id": f"rec_{biz_id}_salaries",
                    "business_id": biz_id,
                    "title": "Staff Salaries & Wages (BACS Payroll)",
                    "category": "salary",
                    "amount": round(daily_base * random.uniform(3.5, 5.0), -1),
                    "frequency": "monthly",
                    "day_of_month": 28,
                    "is_active": True,
                },
                {
                    "id": f"rec_{biz_id}_paye",
                    "business_id": biz_id,
                    "title": "HMRC PAYE & National Insurance Liability",
                    "category": "paye_ni",
                    "amount": round(daily_base * random.uniform(1.0, 1.8), -1),
                    "frequency": "monthly",
                    "day_of_month": 22,
                    "is_active": True,
                },
                {
                    "id": f"rec_{biz_id}_finance",
                    "business_id": biz_id,
                    "title": "Commercial Equipment & Vehicle Finance",
                    "category": "emi",
                    "amount": round(daily_base * random.uniform(0.8, 1.5), -1),
                    "frequency": "monthly",
                    "day_of_month": 10,
                    "is_active": True,
                },
            ]
            recurring_payments.extend(biz_recurring)

            # 3. Simulate Daily Sales, Transactions, Invoices over the entire year
            curr_balance = float(template["init_bal"])
            curr_date = self.start_date
            invoice_counter = 1

            # Drift parameters: sales drop 30% starting in Month 8 (June 2026 onwards)
            drift_start_date = date(2026, 6, 1)

            # Crunch parameters: Specific crunch week in Month 10 (August 2026)
            crunch_start_date = date(2026, 8, 12)
            crunch_end_date = date(2026, 8, 22)

            while curr_date <= self.end_date:
                weekday = curr_date.weekday() # 0 = Monday, 6 = Sunday

                # Weekday factors
                if template["category"] in ["corner_shop", "cafe", "takeaway_restaurant"]:
                    weekday_factor = 1.25 if weekday in [4, 5, 6] else 0.90
                elif template["category"] == "ecommerce_seller":
                    weekday_factor = 1.15 if weekday in [0, 6] else 0.95
                else: # B2B Builder, Manufacturer, Wholesaler
                    weekday_factor = 0.20 if weekday == 6 else (0.50 if weekday == 5 else 1.15)

                # Seasonal multiplier
                event_mult = self.get_festival_multiplier(curr_date, template["category"])

                # Concept drift factor
                drift_factor = 0.70 if (has_drift and curr_date >= drift_start_date) else 1.0

                # Injected crunch factor
                is_crunch_active = (has_crunch and crunch_start_date <= curr_date <= crunch_end_date)
                crunch_sales_factor = 0.40 if is_crunch_active else 1.0

                # Base sales with gentle noise
                noise = random.gauss(1.0, 0.08)
                today_sales = daily_base * weekday_factor * event_mult * drift_factor * crunch_sales_factor * noise
                today_sales = max(today_sales, daily_base * 0.20)

                # Invoice ratio: B2B relies heavily on invoices, retail on card/Faster Payments
                invoice_ratio = random.uniform(0.70, 0.85) if is_b2b else random.uniform(0.05, 0.15)
                daily_invoice_sales = today_sales * invoice_ratio
                daily_direct_sales = today_sales * (1.0 - invoice_ratio)

                # A. Handle Direct Sales (B2C Card / Faster Payments / Cash)
                unbanked_share = template["unbanked_share"]
                unbanked_amount = daily_direct_sales * unbanked_share
                banked_amount = daily_direct_sales * (1.0 - unbanked_share)

                if banked_amount > 0:
                    curr_balance += banked_amount
                    transactions.append({
                        "id": f"tx_{uuid.uuid4().hex[:12]}",
                        "business_id": biz_id,
                        "date": curr_date,
                        "type": "inflow",
                        "category": "sales_digital" if random.random() > 0.15 else "sales_cash_banked",
                        "amount": round(banked_amount, 2),
                        "description": "Daily store takings (Card Merchant / Faster Payments deposit)",
                        "reference_id": None,
                        "is_banked": True,
                        "balance_after": round(curr_balance, 2),
                    })

                if unbanked_amount > 0:
                    transactions.append({
                        "id": f"tx_{uuid.uuid4().hex[:12]}",
                        "business_id": biz_id,
                        "date": curr_date,
                        "type": "inflow",
                        "category": "sales_cash_unbanked",
                        "amount": round(unbanked_amount, 2),
                        "description": "Petty cash retained in shop till / unbanked",
                        "reference_id": None,
                        "is_banked": False,
                        "balance_after": round(curr_balance, 2),
                    })

                # B. Handle Invoices
                min_invoice_size = 600 if is_b2b else 250
                if daily_invoice_sales >= min_invoice_size:
                    cust = random.choice(biz_customers)
                    inv_id = f"inv_{biz_id}_{invoice_counter:04d}"
                    invoice_counter += 1
                    term_days = random.choice([14, 30, 45])
                    due_date = curr_date + timedelta(days=term_days)

                    habit = cust["payment_habit"]
                    if habit == "disciplined":
                        delay = max(0, int(random.gauss(cust["avg_delay_days"], cust["delay_std_days"])))
                    elif habit == "chronic_late":
                        delay = max(5, int(random.gauss(cust["avg_delay_days"], cust["delay_std_days"])))
                    elif habit == "erratic":
                        delay = max(-2, int(random.gauss(cust["avg_delay_days"], cust["delay_std_days"])))
                    else: # seasonal
                        # Pays faster in Q4 rush, slower in winter
                        if curr_date.month in [11, 12, 4]:
                            delay = max(0, int(random.gauss(2, 2)))
                        else:
                            delay = max(10, int(random.gauss(18, 5)))

                    # If crunch active on this business, inject severe customer delay
                    if is_crunch_active and random.random() < 0.65:
                        delay += 35

                    paid_date = due_date + timedelta(days=delay)

                    inv_record = {
                        "id": inv_id,
                        "business_id": biz_id,
                        "customer_id": cust["id"],
                        "invoice_number": f"INV-{curr_date.strftime('%Y%m')}-{invoice_counter:04d}",
                        "amount": round(daily_invoice_sales, 2),
                        "issue_date": curr_date,
                        "due_date": due_date,
                        "paid_date": paid_date,
                        "status": "paid",
                        "actual_delay_days": delay,
                    }
                    invoices.append(inv_record)

                # C. Daily Variable Outflows (Suppliers, inventory replenishment, packaging, utilities)
                if random.random() < 0.45:
                    outflow_amt = round(daily_base * random.uniform(0.20, 0.45), 2)
                    curr_balance -= outflow_amt
                    transactions.append({
                        "id": f"tx_{uuid.uuid4().hex[:12]}",
                        "business_id": biz_id,
                        "date": curr_date,
                        "type": "outflow",
                        "category": "supplier_payment",
                        "amount": outflow_amt,
                        "description": "Stock replenishment / Trade merchant materials",
                        "reference_id": None,
                        "is_banked": True,
                        "balance_after": round(curr_balance, 2),
                    })

                # Injected crunch shock: Surprise large operational deficit on crunch business
                if is_crunch_active and curr_date == (crunch_start_date + timedelta(days=2)):
                    shock_amount = round(template["threshold"] * 1.75, 2)
                    curr_balance -= shock_amount
                    transactions.append({
                        "id": f"tx_{uuid.uuid4().hex[:12]}",
                        "business_id": biz_id,
                        "date": curr_date,
                        "type": "outflow",
                        "category": "other",
                        "amount": shock_amount,
                        "description": "CRUNCH EVENT: Urgent commercial vehicle replacement & major stock supplier margin call",
                        "reference_id": None,
                        "is_banked": True,
                        "balance_after": round(curr_balance, 2),
                    })

                # D. Recurring Monthly Outflows
                for rec in biz_recurring:
                    if curr_date.day == rec["day_of_month"]:
                        curr_balance -= rec["amount"]
                        transactions.append({
                            "id": f"tx_{uuid.uuid4().hex[:12]}",
                            "business_id": biz_id,
                            "date": curr_date,
                            "type": "outflow",
                            "category": rec["category"],
                            "amount": rec["amount"],
                            "description": f"Scheduled: {rec['title']}",
                            "reference_id": rec["id"],
                            "is_banked": True,
                            "balance_after": round(curr_balance, 2),
                        })

                # E. Statutory Quarterly VAT Outflow (due 7th of Feb, May, Aug, Nov)
                if curr_date.day == 7 and curr_date.month in [2, 5, 8, 11]:
                    vat_payment = round(daily_base * random.uniform(2.5, 4.0), -1)
                    curr_balance -= vat_payment
                    transactions.append({
                        "id": f"tx_{uuid.uuid4().hex[:12]}",
                        "business_id": biz_id,
                        "date": curr_date,
                        "type": "outflow",
                        "category": "vat",
                        "amount": vat_payment,
                        "description": "HMRC VAT Return Settlement (Direct Debit / Electronic)",
                        "reference_id": f"vat_{biz_id}_{curr_date.strftime('%Y%m')}",
                        "is_banked": True,
                        "balance_after": round(curr_balance, 2),
                    })

                curr_date += timedelta(days=1)

            # Post-process Invoices:
            for inv in invoices:
                if inv["business_id"] != biz_id:
                    continue
                p_date = inv["paid_date"]
                if p_date <= self.cutoff_date:
                    inv["status"] = "paid"
                    transactions.append({
                        "id": f"tx_{uuid.uuid4().hex[:12]}",
                        "business_id": biz_id,
                        "date": p_date,
                        "type": "inflow",
                        "category": "invoice_collection",
                        "amount": inv["amount"],
                        "description": f"BACS settlement for {inv['invoice_number']}",
                        "reference_id": inv["id"],
                        "is_banked": True,
                        "balance_after": 0.0,
                    })
                else:
                    if inv["due_date"] < self.cutoff_date:
                        inv["status"] = "overdue"
                    else:
                        inv["status"] = "open"

            # Sort transactions chronologically and recalculate accurate running bank balance
            biz_txs = [t for t in transactions if t["business_id"] == biz_id]
            biz_txs.sort(key=lambda x: (x["date"], 0 if x["type"] == "inflow" else 1))

            run_bal = float(template["init_bal"])
            min_observed_bal = run_bal
            for t in biz_txs:
                if t["is_banked"]:
                    if t["type"] == "inflow":
                        run_bal += t["amount"]
                    else:
                        run_bal -= t["amount"]
                t["balance_after"] = round(run_bal, 2)
                if run_bal < min_observed_bal:
                    min_observed_bal = run_bal

            # Safety check: Healthy businesses should never have negative balances
            # If a healthy business dipped below zero due to stochastic noise, adjust initial balance and shift run_bal
            if not has_crunch and min_observed_bal < 0:
                deficit = abs(min_observed_bal) + 5000.0
                template["init_bal"] += deficit
                biz_record["initial_balance"] = float(template["init_bal"])
                # Re-offset all balance_after
                for t in biz_txs:
                    t["balance_after"] = round(t["balance_after"] + deficit, 2)
                run_bal += deficit

            biz_record["current_balance"] = round(run_bal, 2)
            businesses.append(biz_record)

        return {
            "businesses": businesses,
            "customers": customers,
            "invoices": invoices,
            "recurring_payments": recurring_payments,
            "transactions": transactions,
        }
