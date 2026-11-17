import os
import sys
import json
from datetime import date, datetime

# Add app parent directory to sys.path so it works directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.models.database import engine, Base, SessionLocal
from app.models.schema import Business, Customer, Invoice, RecurringPayment, Transaction
from app.data.generator import SyntheticDataGenerator

def seed_database():
    print("Creating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    print("Generating synthetic data for 30 SMEs across the United Kingdom...")
    gen = SyntheticDataGenerator(seed=42)
    data = gen.generate_all_data()

    db = SessionLocal()
    try:
        # Insert businesses
        print(f"Inserting {len(data['businesses'])} businesses...")
        for b in data["businesses"]:
            db.add(Business(**b))
        db.flush()

        # Insert customers
        print(f"Inserting {len(data['customers'])} customers...")
        for c in data["customers"]:
            db.add(Customer(**c))
        db.flush()

        # Insert recurring payments
        print(f"Inserting {len(data['recurring_payments'])} recurring payments...")
        for r in data["recurring_payments"]:
            db.add(RecurringPayment(**r))
        db.flush()

        # Insert invoices
        print(f"Inserting {len(data['invoices'])} invoices...")
        for inv in data["invoices"]:
            db.add(Invoice(**inv))
        db.flush()

        # Insert transactions in batches of 1000 for speed
        print(f"Inserting {len(data['transactions'])} transactions...")
        batch_size = 1000
        for i in range(0, len(data["transactions"]), batch_size):
            batch = data["transactions"][i:i+batch_size]
            db.bulk_insert_mappings(Transaction, batch)
            db.flush()

        db.commit()
        print("Database seeded successfully!")

        # Print data summary
        print("\n" + "="*50)
        print("CASHLOOP UK SME SYNTHETIC DATASET SUMMARY")
        print("="*50)
        print(f"Businesses:         {db.query(Business).count()}")
        print(f"Customers:          {db.query(Customer).count()}")
        print(f"Recurring Payments: {db.query(RecurringPayment).count()}")
        print(f"Invoices:           {db.query(Invoice).count()}")
        print(f"Transactions:       {db.query(Transaction).count()}")
        print("="*50)

        # Print a sample business profile
        sample_biz = db.query(Business).first()
        print(f"\nSAMPLE BUSINESS DETAILS ({sample_biz.id}):")
        print(f"Name:               {sample_biz.name}")
        print(f"Category:           {sample_biz.category}")
        print(f"City, Region:       {sample_biz.city}, {sample_biz.state}")
        print(f"VAT Number:         {sample_biz.vat_number}")
        print(f"Min Cash Threshold: £{sample_biz.min_cash_threshold:,.2f}")
        print(f"Initial Balance:    £{sample_biz.initial_balance:,.2f}")
        print(f"Current Balance:    £{sample_biz.current_balance:,.2f}")
        print(f"Unbanked Cash:      {sample_biz.unbanked_cash_share * 100:.0f}%")
        print(f"Injected Crunch:    {sample_biz.has_crunch_injected}")
        print(f"Concept Drift:      {sample_biz.has_drift}")

        # Invoices for sample biz
        open_invs = db.query(Invoice).filter(Invoice.business_id == sample_biz.id, Invoice.status != "paid").count()
        paid_invs = db.query(Invoice).filter(Invoice.business_id == sample_biz.id, Invoice.status == "paid").count()
        print(f"Invoices:           {paid_invs} paid, {open_invs} pending/overdue")

        # Recurring expenses for sample biz
        recs = db.query(RecurringPayment).filter(RecurringPayment.business_id == sample_biz.id).all()
        print("Monthly Recurring Outflows:")
        for r in recs:
            print(f"  - {r.title} (Day {r.day_of_month}): £{r.amount:,.2f}")

        # Transactions count
        tx_count = db.query(Transaction).filter(Transaction.business_id == sample_biz.id).count()
        print(f"Total Transactions: {tx_count}")
        print("="*50 + "\n")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
