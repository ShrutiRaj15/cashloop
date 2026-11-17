#!/usr/bin/env python3
"""
Database Reset & Reseed Script for CashLoop
Drops all tables, recreates schema, and reseeds synthetic data cleanly.
"""
import os
import sys

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.models.database import engine, Base, SessionLocal
from app.data.seed import seed_database

def reset_db():
    print("[reset_db] Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("[reset_db] Recreating all tables...")
    Base.metadata.create_all(bind=engine)
    print("[reset_db] Reseeding data...")
    seed_database()
    print("[reset_db] Database reset and reseed complete.")

if __name__ == "__main__":
    reset_db()
