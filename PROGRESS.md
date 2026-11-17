# CashLoop Progress Tracker

## Status Overview
- Current Stage: Stage 2 (UK Basis)
- Market: Refactoring from Indian MSME to UK SME basis
- Baseline commit: `cd533690` ("baseline before UK refactor")

---

## Stages

### [DONE] Stage 1 - Remove Hindi Completely
- [x] Remove language toggle and all `lang` prop/state from frontend components (`page.tsx`, `Navbar.tsx`, `CashChart.tsx`, `RecommendationsList.tsx`, `InvoicesList.tsx`, `LenderView.tsx`, `LoopDashboardView.tsx`, `InvoiceExtractorModal.tsx`, `ClosedLoopMetrics.tsx`).
- [x] Backend: remove Hindi text generation, the `description_hi` column/field from models/schemas/seed/recommendations.
- [x] Backend: remove `lang` query parameter from `/api/explanations/{business_id}` and `app/services/llm.py`.
- [x] Remove all Hindi branches in `app/services/llm.py` and `app/services/recommendations.py`.
- [x] Verify no Devanagari characters remain in `frontend/src` or `backend/app`.
- [x] Create `backend/scripts/reset_db.py` to drop and recreate DB cleanly without manual deletion.
- [x] Run backend pytest suite and frontend `npm run build`. Smoke test endpoints and pages.
- [x] Commit: `stage 1: remove Hindi completely`.

### [IN PROGRESS] Stage 2 - UK Basis
- [ ] Centralise market settings in `backend/app/config.py` and `frontend/src/lib/format.ts` (GBP, `en-GB`, formatMoney / formatDate helpers). Replace every hardcoded rupee symbol, `en-IN` formatting, and lakh/crore wording.
- [ ] Terminology replacement:
  - GST / GSTIN -> VAT / VAT number
  - Business ID -> Companies House number (8 alphanumeric characters, e.g., `01234567` or `SC123456`)
  - MSME / NBFC -> SME / lender
  - UPI / TReDS / Account Aggregator -> Faster Payments / BACS / Open Banking / invoice finance
  - Remove "Indian" from all titles, subtitles, and metadata.
- [ ] Data generator updates (`app/data/generator.py`):
  - UK business types: corner shop, cafe, takeaway/restaurant, tradesperson/builder, e-commerce seller, small manufacturer, wholesaler.
  - UK-style business names, UK cities and postcodes.
  - Realistic GBP scale (weekly takings in the low thousands of pounds).
  - Calendar features: UK bank holidays, Christmas, Easter, Black Friday, school holidays (replace Diwali/Holi/Eid).
- [ ] Tax calendar in config:
  - VAT quarterly return and payment (due 1 month + 7 days after quarter end).
  - PAYE / NI monthly (due on the 22nd for electronic payment).
  - Corporation tax notes pointing to gov.uk source and "verify before production" note.
- [ ] Data calibration:
  - Opening balances positive (roughly 20–40 days of average outflow).
  - Only 3–4 of the 30 businesses get an injected cash crunch; most are healthy; no healthy business should show a negative balance.
- [ ] Reset DB via `backend/scripts/reset_db.py`, reseed, and rerun simulation. Save results in `backend/reports/simulation_report.md`.
- [ ] Add clear "synthetic data" notice in the UI.
- [ ] Run pytest, `npm run build`, smoke test backend & frontend.
- [ ] Commit: `stage 2: UK basis`.

---

## Decisions
- Kept English UI copy with UK spelling (e.g., categorise, amortisation, programme, colour).
- Created `backend/scripts/reset_db.py` to manage database schema updates idempotently according to safety rules.
- Set up root `.gitignore` to prevent committing build caches.

## Known Issues
- None at present.
