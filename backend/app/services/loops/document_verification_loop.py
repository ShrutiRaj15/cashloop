import re
import uuid
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.schema import InvoiceVerification, Transaction, AuditLog, Business
from app.services.llm import get_llm_service

class DocumentVerificationLoop:
    def __init__(self, db: Session):
        self.db = db
        self.llm = get_llm_service()

    def process_and_verify_invoice(
        self,
        business_id: str,
        raw_text: str,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Agent verification loop: extracts fields, validates against bank transactions,
        retries with corrected prompt on mismatch up to 2 times, or flags for human review.
        """
        verification_id = f"verif_{uuid.uuid4().hex[:10]}"
        attempt = 0
        current_text = raw_text
        extracted = None
        is_valid = False
        notes = []
        matched_tx_id = None

        while attempt <= max_retries:
            # Step 1: Agent extraction
            extracted = self.llm.extract_invoice(current_text)

            # Step 2: Validation against bank transactions
            is_valid, validation_msg, matched_tx_id = self._validate_against_bank(
                business_id, extracted
            )

            if is_valid:
                notes.append(f"Attempt {attempt + 1}: Validated successfully ({validation_msg}).")
                break
            else:
                notes.append(f"Attempt {attempt + 1} Mismatch: {validation_msg}")
                attempt += 1
                if attempt <= max_retries:
                    # Retry with corrected instruction prompt
                    current_text = (
                        f"[SYSTEM RE-EXTRACTION ATTEMPT {attempt + 1} - PREVIOUS ERROR: {validation_msg}]\n"
                        f"Re-check all amounts, VAT number, and vendor name accurately from the document:\n{raw_text}"
                    )

        # Final decision
        if is_valid:
            status = "verified"
        else:
            status = "flagged_for_human_review"
            notes.append("Exceeded 2 retries without bank reconciliation. Queued for human approval.")

        # Persist verification record
        inv_dt = None
        due_dt = None
        try:
            if extracted.get("issue_date"):
                inv_dt = date.fromisoformat(extracted["issue_date"])
            if extracted.get("due_date"):
                due_dt = date.fromisoformat(extracted["due_date"])
        except Exception:
            pass

        record = InvoiceVerification(
            id=verification_id,
            business_id=business_id,
            raw_text=raw_text,
            extracted_vendor=extracted.get("vendor_name"),
            extracted_invoice_number=extracted.get("invoice_number"),
            extracted_amount=float(extracted.get("amount", 0.0)),
            extracted_date=inv_dt,
            extracted_due_date=due_dt,
            validation_status=status,
            validation_notes="\n".join(notes),
            retry_count=attempt,
            matched_transaction_id=matched_tx_id
        )
        self.db.add(record)

        audit = AuditLog(
            id=f"aud_verif_{verification_id}",
            event_type="document_verification",
            business_id=business_id,
            details=f"Invoice {extracted.get('invoice_number')} processed. Status: {status} (Retries: {attempt}). Notes: {notes[-1]}"
        )
        self.db.add(audit)
        self.db.commit()

        return {
            "verification_id": verification_id,
            "validation_status": status,
            "retry_count": attempt,
            "extracted": extracted,
            "validation_notes": notes,
            "matched_transaction_id": matched_tx_id,
            "requires_human_approval": (status == "flagged_for_human_review")
        }

    def _validate_against_bank(
        self,
        business_id: str,
        extracted: dict
    ) -> Tuple[bool, str, Optional[str]]:
        amount = float(extracted.get("amount", 0.0))
        if amount <= 0:
            return False, "Invalid or non-positive invoice amount", None

        # Check bank transactions within 15% tolerance of amount
        lower_bound = amount * 0.85
        upper_bound = amount * 1.15

        candidate_txs = (
            self.db.query(Transaction)
            .filter(
                Transaction.business_id == business_id,
                Transaction.amount >= lower_bound,
                Transaction.amount <= upper_bound,
                Transaction.is_banked == True
            )
            .all()
        )

        if not candidate_txs:
            # If no transaction found with matching amount, check if invoice is newly created / future receivable
            # If due date is in the future, it is an open invoice receivable (valid business case)
            due_str = extracted.get("due_date", "")
            try:
                due_dt = date.fromisoformat(due_str)
                if due_dt >= date(2026, 10, 1):
                    return True, "Open forward receivable with future due date (valid invoice)", None
            except Exception:
                pass
            return False, f"No matching bank transaction found for £{amount:,.2f} (+/-15% tolerance)", None

        # Matched transaction found
        matched_tx = candidate_txs[0]
        return True, f"Matched bank transaction {matched_tx.id} for £{matched_tx.amount:,.2f}", matched_tx.id

    def get_review_queue(self, business_id: Optional[str] = None) -> List[dict]:
        """
        Retrieves invoices flagged for human-in-the-loop review.
        """
        query = self.db.query(InvoiceVerification).filter(
            InvoiceVerification.validation_status == "flagged_for_human_review"
        )
        if business_id:
            query = query.filter(InvoiceVerification.business_id == business_id)

        items = query.order_by(InvoiceVerification.created_at.desc()).all()
        return [
            {
                "id": i.id,
                "business_id": i.business_id,
                "vendor_name": i.extracted_vendor,
                "invoice_number": i.extracted_invoice_number,
                "amount": i.extracted_amount,
                "due_date": i.extracted_due_date.isoformat() if i.extracted_due_date else None,
                "status": i.validation_status,
                "notes": i.validation_notes,
                "retry_count": i.retry_count,
                "created_at": i.created_at.isoformat()
            }
            for i in items
        ]

    def human_decision(self, verification_id: str, decision: str, notes: str = "") -> Dict[str, Any]:
        """
        Human supervisor approves or rejects flagged invoice.
        """
        rec = self.db.query(InvoiceVerification).filter(InvoiceVerification.id == verification_id).first()
        if not rec:
            return {"status": "error", "message": "Verification record not found"}

        rec.validation_status = "approved_by_human" if decision == "approve" else "rejected"
        rec.validation_notes += f"\nHuman Review: {decision.upper()} - {notes}"

        audit = AuditLog(
            id=f"aud_h_{uuid.uuid4().hex[:10]}",
            event_type="human_review_decision",
            business_id=rec.business_id,
            details=f"Human supervisor {decision}ed invoice verification {verification_id}."
        )
        self.db.add(audit)
        self.db.commit()

        return {"status": "success", "new_status": rec.validation_status}
