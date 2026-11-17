import csv
import io
import uuid
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schema import Business, Transaction, AuditLog

router = APIRouter(prefix="/statements", tags=["statements"])

@router.post("/upload")
async def upload_bank_statement(
    business_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a CSV bank statement.")

    content = await file.read()
    if not content or len(content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Bank statement file is empty.")

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed file encoding. Please upload UTF-8 encoded CSV.")

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file contains no headers.")

    # Normalize header names
    field_map = {f.lower().strip().replace(" ", "_"): f for f in reader.fieldnames}
    date_col = next((field_map[k] for k in ["date", "txn_date", "transaction_date"] if k in field_map), None)
    amt_col = next((field_map[k] for k in ["amount", "txn_amount", "value"] if k in field_map), None)
    type_col = next((field_map[k] for k in ["type", "txn_type", "cr_dr"] if k in field_map), None)
    desc_col = next((field_map[k] for k in ["description", "narration", "particulars"] if k in field_map), None)

    if not date_col or not amt_col:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns in CSV. Required: 'date' and 'amount'. Found headers: {reader.fieldnames}"
        )

    parsed_transactions = []
    running_balance = biz.current_balance
    row_num = 1

    for row in reader:
        row_num += 1
        raw_date = row.get(date_col, "").strip()
        raw_amt = row.get(amt_col, "").strip().replace(",", "").replace("₹", "").replace("Rs.", "")
        raw_type = row.get(type_col, "inflow").strip().lower() if type_col else "inflow"
        raw_desc = row.get(desc_col, "Bank statement entry").strip() if desc_col else "Bank statement entry"

        if not raw_date or not raw_amt:
            continue

        # Parse date
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed_date = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue

        if not parsed_date:
            raise HTTPException(status_code=400, detail=f"Row {row_num}: Invalid date format '{raw_date}'. Use YYYY-MM-DD or DD-MM-YYYY.")

        # Parse amount
        try:
            amt = abs(float(raw_amt))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Row {row_num}: Invalid numeric amount '{raw_amt}'.")

        # Normalize type
        is_inflow = raw_type in ["inflow", "cr", "credit", "deposit"]
        txn_type = "inflow" if is_inflow else "outflow"

        if is_inflow:
            running_balance += amt
        else:
            running_balance -= amt

        tx_id = f"tx_up_{uuid.uuid4().hex[:10]}"
        parsed_transactions.append(Transaction(
            id=tx_id,
            business_id=business_id,
            date=parsed_date,
            type=txn_type,
            category="sales_digital" if is_inflow else "supplier_payment",
            amount=amt,
            description=raw_desc,
            is_banked=True,
            balance_after=round(running_balance, 2)
        ))

    if not parsed_transactions:
        raise HTTPException(status_code=400, detail="No valid transactions parsed from CSV.")

    # Bulk insert
    db.add_all(parsed_transactions)
    biz.current_balance = round(running_balance, 2)

    audit = AuditLog(
        id=f"aud_csv_{uuid.uuid4().hex[:10]}",
        event_type="statement_uploaded",
        business_id=business_id,
        details=f"Uploaded CSV statement '{file.filename}'. Imported {len(parsed_transactions)} transactions. New balance: ₹{running_balance:,.2f}."
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "transactions_imported": len(parsed_transactions),
        "new_balance": round(running_balance, 2),
        "first_date": parsed_transactions[0].date.isoformat(),
        "last_date": parsed_transactions[-1].date.isoformat()
    }
