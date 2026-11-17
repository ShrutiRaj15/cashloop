import os
import sys
import pytest
from datetime import date

# Set test database path before imports
os.environ["CASHLOOP_DB_PATH"] = os.path.join(os.path.dirname(__file__), "test_cashloop.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.data.generator import SyntheticDataGenerator
from app.models.database import engine, Base, SessionLocal
from app.models.schema import Business, Customer, Invoice, RecurringPayment, Transaction

@pytest.fixture(scope="module")
def dataset():
    gen = SyntheticDataGenerator(seed=123)
    return gen.generate_all_data()

def test_business_count_and_categories(dataset):
    businesses = dataset["businesses"]
    assert len(businesses) == 30, "Should generate exactly 30 businesses"
    categories = {b["category"] for b in businesses}
    expected_categories = {"kirana", "sweet_shop", "garment_wholesaler", "small_manufacturer"}
    assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"

def test_injected_crunches_and_drift(dataset):
    businesses = dataset["businesses"]
    crunches = [b for b in businesses if b["has_crunch_injected"]]
    drifts = [b for b in businesses if b["has_drift"]]
    assert len(crunches) >= 4, f"Expected at least 4 crunch businesses, got {len(crunches)}"
    assert len(drifts) >= 4, f"Expected at least 4 drift businesses, got {len(drifts)}"

def test_recurring_payments_rules(dataset):
    recurring = dataset["recurring_payments"]
    assert len(recurring) > 0
    # Every business should have a salary on the 5th and GST on the 20th
    biz_ids = {b["id"] for b in dataset["businesses"]}
    for b_id in biz_ids:
        biz_rec = [r for r in recurring if r["business_id"] == b_id]
        days = {r["day_of_month"] for r in biz_rec}
        categories = {r["category"] for r in biz_rec}
        assert 5 in days, f"Business {b_id} missing salary payment on 5th"
        assert 20 in days, f"Business {b_id} missing GST payment on 20th"
        assert "salary" in categories
        assert "gst" in categories

def test_customer_habits(dataset):
    customers = dataset["customers"]
    assert len(customers) >= 150
    habits = {c["payment_habit"] for c in customers}
    expected_habits = {"disciplined", "chronic_late", "erratic", "seasonal"}
    assert expected_habits == habits

    # Chronic late customers should have significantly higher average delay
    chronic = [c for c in customers if c["payment_habit"] == "chronic_late"]
    disciplined = [c for c in customers if c["payment_habit"] == "disciplined"]
    assert sum(c["avg_delay_days"] for c in chronic) / len(chronic) > 15
    assert sum(c["avg_delay_days"] for c in disciplined) / len(disciplined) < 5

def test_unbanked_cash_and_transactions(dataset):
    txs = dataset["transactions"]
    assert len(txs) > 10000
    unbanked_txs = [t for t in txs if not t["is_banked"]]
    banked_txs = [t for t in txs if t["is_banked"]]
    assert len(unbanked_txs) > 0, "Should generate unbanked cash transactions"
    assert len(banked_txs) > 0, "Should generate banked cash transactions"

    # All unbanked transactions must have category sales_cash_unbanked
    for ut in unbanked_txs[:50]:
        assert ut["category"] == "sales_cash_unbanked"

def test_festival_spikes():
    gen = SyntheticDataGenerator(seed=42)
    # Check sweet shop festive multiplier on Diwali (Nov 1, 2025) vs off-season (July 15, 2026)
    diwali_mult = gen.get_festival_multiplier(date(2025, 11, 1), "sweet_shop")
    normal_mult = gen.get_festival_multiplier(date(2026, 7, 15), "sweet_shop")
    assert diwali_mult >= 2.5
    assert normal_mult == 1.0

def test_db_seeding_and_integrity():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    mem_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=mem_engine)
    MemSession = sessionmaker(bind=mem_engine)
    
    gen = SyntheticDataGenerator(seed=999)
    data = gen.generate_all_data()

    db = MemSession()
    try:
        for b in data["businesses"]:
            db.add(Business(**b))
        for c in data["customers"]:
            db.add(Customer(**c))
        for r in data["recurring_payments"]:
            db.add(RecurringPayment(**r))
        for inv in data["invoices"]:
            db.add(Invoice(**inv))
        db.bulk_insert_mappings(Transaction, data["transactions"])
        db.commit()

        # Query back
        assert db.query(Business).count() == 30
        assert db.query(Customer).count() == len(data["customers"])
        assert db.query(Invoice).count() == len(data["invoices"])
        assert db.query(Transaction).count() == len(data["transactions"])
        assert db.query(RecurringPayment).count() == len(data["recurring_payments"])
    finally:
        db.close()
