from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models.database import get_db
from app.models.schema import Business, BusinessBase, Transaction, TransactionBase

router = APIRouter(prefix="/businesses", tags=["businesses"])

@router.get("", response_model=List[BusinessBase])
def list_businesses(db: Session = Depends(get_db)):
    return db.query(Business).all()

@router.get("/{business_id}", response_model=BusinessBase)
def get_business(business_id: str, db: Session = Depends(get_db)):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    return biz

@router.get("/{business_id}/transactions")
def get_business_transactions(business_id: str, limit: int = 100, db: Session = Depends(get_db)):
    txs = (
        db.query(Transaction)
        .filter(Transaction.business_id == business_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "type": t.type,
            "category": t.category,
            "amount": t.amount,
            "description": t.description,
            "is_banked": t.is_banked,
            "balance_after": t.balance_after
        }
        for t in txs
    ]
