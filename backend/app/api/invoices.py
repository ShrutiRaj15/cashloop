from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

from app.models.database import get_db
from app.models.schema import Invoice, Customer, Business
from app.ml.invoice_delay import InvoiceDelayModel
from app.services.llm import get_llm_service

router = APIRouter(prefix="/invoices", tags=["invoices"])

class InvoiceExtractRequest(BaseModel):
    raw_text: str

@router.get("/{business_id}")
def get_invoices(business_id: str, status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Invoice).filter(Invoice.business_id == business_id)
    if status:
        query = query.filter(Invoice.status == status)
    
    invoices = query.order_by(Invoice.issue_date.desc()).all()
    customers = db.query(Customer).filter(Customer.business_id == business_id).all()
    cust_map = {c.id: c for c in customers}

    # Run delay model on open invoices
    hist_invoices = [
        {"id": i.id, "customer_id": i.customer_id, "amount": i.amount, "issue_date": i.issue_date, "due_date": i.due_date, "actual_delay_days": i.actual_delay_days}
        for i in invoices if i.status == "paid"
    ]
    open_invs = [
        {"id": i.id, "invoice_number": i.invoice_number, "customer_id": i.customer_id, "amount": i.amount, "issue_date": i.issue_date, "due_date": i.due_date}
        for i in invoices if i.status != "paid"
    ]
    cust_dicts = [
        {"id": c.id, "name": c.name, "payment_habit": c.payment_habit, "avg_delay_days": c.avg_delay_days, "delay_std_days": c.delay_std_days}
        for c in customers
    ]

    delay_model = InvoiceDelayModel()
    delay_model.fit(hist_invoices, cust_dicts)
    predictions = delay_model.predict_delays(open_invs, cust_dicts)
    pred_map = {p["invoice_id"]: p for p in predictions}

    results = []
    for inv in invoices:
        c = cust_map.get(inv.customer_id)
        pred = pred_map.get(inv.id)
        results.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "customer_name": c.name if c else "Unknown Customer",
            "customer_habit": c.payment_habit if c else "disciplined",
            "amount": inv.amount,
            "issue_date": inv.issue_date.isoformat(),
            "due_date": inv.due_date.isoformat(),
            "paid_date": inv.paid_date.isoformat() if inv.paid_date else None,
            "status": inv.status,
            "actual_delay_days": inv.actual_delay_days,
            "expected_payment_date": pred["expected_payment_date"].isoformat() if pred and pred.get("expected_payment_date") else None,
            "delay_p50": pred["delay_p50"] if pred else None
        })

    return results

@router.post("/extract")
def extract_invoice_data(payload: InvoiceExtractRequest):
    llm = get_llm_service()
    extracted = llm.extract_invoice(payload.raw_text)
    return extracted

class InvoiceUploadRequest(BaseModel):
    business_id: str
    raw_text: str

class HumanReviewDecisionRequest(BaseModel):
    decision: str # approve, reject
    notes: Optional[str] = ""

@router.post("/upload")
def upload_and_verify_invoice(payload: InvoiceUploadRequest, db: Session = Depends(get_db)):
    from app.services.loops.document_verification_loop import DocumentVerificationLoop
    loop = DocumentVerificationLoop(db)
    result = loop.process_and_verify_invoice(
        business_id=payload.business_id,
        raw_text=payload.raw_text
    )
    return result

@router.get("/review-queue/all")
def get_review_queue(business_id: Optional[str] = None, db: Session = Depends(get_db)):
    from app.services.loops.document_verification_loop import DocumentVerificationLoop
    loop = DocumentVerificationLoop(db)
    return loop.get_review_queue(business_id)

@router.post("/review-queue/{verification_id}/decide")
def submit_human_decision(
    verification_id: str,
    payload: HumanReviewDecisionRequest,
    db: Session = Depends(get_db)
):
    from app.services.loops.document_verification_loop import DocumentVerificationLoop
    loop = DocumentVerificationLoop(db)
    return loop.human_decision(
        verification_id=verification_id,
        decision=payload.decision,
        notes=payload.notes or ""
    )
