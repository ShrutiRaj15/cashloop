import enum
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Date, DateTime, 
    ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict
from app.models.database import Base

# SQLAlchemy Models

class BusinessCategory(str, enum.Enum):
    CORNER_SHOP = "corner_shop"
    CAFE = "cafe"
    TAKEAWAY_RESTAURANT = "takeaway_restaurant"
    TRADESPERSON_BUILDER = "tradesperson_builder"
    ECOMMERCE_SELLER = "ecommerce_seller"
    SMALL_MANUFACTURER = "small_manufacturer"
    WHOLESALER = "wholesaler"
    # Legacy aliases
    KIRANA = "corner_shop"
    SWEET_SHOP = "cafe"
    GARMENT_WHOLESALER = "wholesaler"

class PaymentHabit(str, enum.Enum):
    DISCIPLINED = "disciplined"       # Pays on time (0-3 days)
    CHRONIC_LATE = "chronic_late"     # Always ~15-25 days late
    ERRATIC = "erratic"               # Highly variable (-5 to +35 days)
    SEASONAL = "seasonal"             # Pays fast during peak season, slow otherwise

class InvoiceStatus(str, enum.Enum):
    OPEN = "open"
    PAID = "paid"
    OVERDUE = "overdue"

class TransactionCategory(str, enum.Enum):
    SALES_DIGITAL = "sales_digital"
    SALES_CASH_BANKED = "sales_cash_banked"
    SALES_CASH_UNBANKED = "sales_cash_unbanked"
    INVOICE_COLLECTION = "invoice_collection"
    SALARY = "salary"
    RENT = "rent"
    EMI = "emi"
    VAT = "vat"
    GST = "vat"
    PAYE_NI = "paye_ni"
    SUPPLIER_PAYMENT = "supplier_payment"
    UTILITY = "utility"
    OTHER = "other"

class Business(Base):
    __tablename__ = "businesses"

    id = Column(String, primary_key=True, index=True) # Companies House Number (8 alphanumeric chars)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False) # UK Region / County
    vat_number = Column(String, nullable=False, default="")
    gstin = Column(String, nullable=True) # Legacy compatibility
    min_cash_threshold = Column(Float, default=5000.0)
    initial_balance = Column(Float, default=25000.0)
    current_balance = Column(Float, default=25000.0)
    unbanked_cash_share = Column(Float, default=0.10)
    has_drift = Column(Boolean, default=False)
    has_crunch_injected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    customers = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="business", cascade="all, delete-orphan")
    recurring_payments = relationship("RecurringPayment", back_populates="business", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="business", cascade="all, delete-orphan")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    payment_habit = Column(String, default="disciplined")
    avg_delay_days = Column(Float, default=0.0)
    delay_std_days = Column(Float, default=3.0)
    initial_delay_std = Column(Float, default=5.0)
    observations_count = Column(Integer, default=1)
    credit_limit = Column(Float, default=100000.0)
    phone = Column(String, nullable=True)

    business = relationship("Business", back_populates="customers")
    invoices = relationship("Invoice", back_populates="customer", cascade="all, delete-orphan")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False, index=True)
    invoice_number = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date, nullable=True)
    status = Column(String, default="open") # open, paid, overdue
    actual_delay_days = Column(Integer, nullable=True)

    business = relationship("Business", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")

class RecurringPayment(Base):
    __tablename__ = "recurring_payments"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False) # rent, salary, emi, gst, supplier
    amount = Column(Float, nullable=False)
    frequency = Column(String, default="monthly")
    day_of_month = Column(Integer, nullable=False) # e.g. 5 for salaries, 20 for GST
    is_active = Column(Boolean, default=True)

    business = relationship("Business", back_populates="recurring_payments")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    type = Column(String, nullable=False) # inflow, outflow
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    reference_id = Column(String, nullable=True)
    is_banked = Column(Boolean, default=True)
    balance_after = Column(Float, nullable=False)

    business = relationship("Business", back_populates="transactions")


# Pydantic Schemas for API / serialization

class BusinessBase(BaseModel):
    id: str
    name: str
    category: str
    city: str
    state: str
    vat_number: str
    gstin: Optional[str] = None
    min_cash_threshold: float
    initial_balance: float
    current_balance: float
    unbanked_cash_share: float
    has_drift: bool
    has_crunch_injected: bool

    model_config = ConfigDict(from_attributes=True)

class CustomerBase(BaseModel):
    id: str
    business_id: str
    name: str
    payment_habit: str
    avg_delay_days: float
    delay_std_days: float
    credit_limit: float

    model_config = ConfigDict(from_attributes=True)

class InvoiceBase(BaseModel):
    id: str
    business_id: str
    customer_id: str
    invoice_number: str
    amount: float
    issue_date: date
    due_date: date
    paid_date: Optional[date] = None
    status: str
    actual_delay_days: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class RecurringPaymentBase(BaseModel):
    id: str
    business_id: str
    title: str
    category: str
    amount: float
    frequency: str
    day_of_month: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class TransactionBase(BaseModel):
    id: str
    business_id: str
    date: date
    type: str
    category: str
    amount: float
    description: str
    reference_id: Optional[str] = None
    is_banked: bool
    balance_after: float

    model_config = ConfigDict(from_attributes=True)

class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    prediction_date = Column(Date, nullable=False, index=True)
    target_date = Column(Date, nullable=False, index=True)
    horizon_days = Column(Integer, nullable=False)
    predicted_p10 = Column(Float, nullable=False)
    predicted_p50 = Column(Float, nullable=False)
    predicted_p90 = Column(Float, nullable=False)
    predicted_naive = Column(Float, nullable=False)
    actual_balance = Column(Float, nullable=True)
    absolute_error = Column(Float, nullable=True)
    ape = Column(Float, nullable=True)
    is_inside_interval = Column(Boolean, nullable=True)
    status = Column(String, default="pending") # pending, evaluated

class ActionRecommendation(Base):
    __tablename__ = "action_recommendations"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    created_date = Column(Date, nullable=False, index=True)
    danger_date = Column(Date, nullable=False)
    action_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    description_en = Column(Text, nullable=True)
    estimated_cost = Column(Float, nullable=False)
    cash_unlocked = Column(Float, nullable=False)
    net_benefit = Column(Float, nullable=False)
    bandit_arm = Column(String, default="default")
    bandit_score = Column(Float, default=1.0)
    status = Column(String, default="proposed") # proposed, accepted, rejected, executed
    execution_date = Column(Date, nullable=True)
    outcome = Column(String, nullable=True) # shortfall_averted, shortfall_mitigated, missed

class DriftEvent(Base):
    __tablename__ = "drift_events"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    event_date = Column(Date, nullable=False, index=True)
    trigger_type = Column(String, default="drift") # drift, cusum, scheduled
    rolling_wape_before = Column(Float, nullable=False)
    rolling_wape_after = Column(Float, nullable=True)
    reason = Column(String, nullable=False)
    retrain_success = Column(Boolean, default=True)

class InvoiceVerification(Base):
    __tablename__ = "invoice_verifications"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    raw_text = Column(Text, nullable=False)
    extracted_vendor = Column(String, nullable=True)
    extracted_invoice_number = Column(String, nullable=True)
    extracted_amount = Column(Float, nullable=True)
    extracted_vat_number = Column(String, nullable=True)
    extracted_gstin = Column(String, nullable=True)
    extracted_date = Column(Date, nullable=True)
    extracted_due_date = Column(Date, nullable=True)
    validation_status = Column(String, default="pending") # verified, flagged_for_human_review, approved_by_human, rejected
    validation_notes = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    matched_transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class LenderIntervention(Base):
    __tablename__ = "lender_interventions"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    intervention_date = Column(Date, nullable=False, index=True)
    intervention_type = Column(String, nullable=False) # reminder_sent, credit_line_offered, loan_restructure, working_capital_topup
    predicted_shortfall = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, default="active") # active, completed
    outcome = Column(String, default="pending") # avoided, defaulted, pending
    resolved_date = Column(Date, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String, nullable=False, index=True)
    business_id = Column(String, nullable=True, index=True)
    details = Column(Text, nullable=False)

class PredictionLogBase(BaseModel):
    id: str
    business_id: str
    prediction_date: date
    target_date: date
    horizon_days: int
    predicted_p10: float
    predicted_p50: float
    predicted_p90: float
    predicted_naive: float
    actual_balance: Optional[float] = None
    absolute_error: Optional[float] = None
    ape: Optional[float] = None
    is_inside_interval: Optional[bool] = None
    status: str

    model_config = ConfigDict(from_attributes=True)

class ActionRecommendationBase(BaseModel):
    id: str
    business_id: str
    created_date: date
    danger_date: date
    action_type: str
    title: str
    description: str
    description_en: Optional[str] = None
    estimated_cost: float
    cash_unlocked: float
    net_benefit: float
    status: str
    execution_date: Optional[date] = None
    outcome: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class DriftEventBase(BaseModel):
    id: str
    business_id: str
    event_date: date
    rolling_wape_before: float
    reason: str
    retrain_success: bool

    model_config = ConfigDict(from_attributes=True)
