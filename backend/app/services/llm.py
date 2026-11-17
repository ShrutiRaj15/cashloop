import os
import re
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLMProvider(ABC):
    @abstractmethod
    def explain_cash_flow(self, business: dict, forecast: dict, language: str = "en") -> str:
        pass

    @abstractmethod
    def explain_recommendation(self, business: dict, action: dict, language: str = "en") -> str:
        pass

    @abstractmethod
    def extract_invoice(self, raw_text: str) -> Dict[str, Any]:
        pass

class MockLLMProvider(LLMProvider):
    def explain_cash_flow(self, business: dict, forecast: dict, language: str = "en") -> str:
        biz_name = business.get("name", "Your Business")
        danger_count = forecast.get("danger_days_count", 0)
        first_danger = forecast.get("first_danger_date", "upcoming days")
        max_shortfall = forecast.get("max_shortfall", 0.0)
        threshold = forecast.get("min_cash_threshold", 25000.0)
        min_p50 = forecast.get("min_projected_balance_p50", 0.0)
        driver = forecast.get("primary_driver", "scheduled monthly obligations")

        if danger_count == 0:
            return (
                f"Hello {biz_name}! Your 30-day cash flow projection is currently healthy. "
                f"Your lowest projected balance is £{min_p50:,.2f}, which comfortably exceeds your safety threshold of £{threshold:,.2f}."
            )
        return (
            f"Early Warning Alert for {biz_name}: A projected cash shortfall of £{max_shortfall:,.2f} is expected around {first_danger}. "
            f"Your balance is forecasted to dip to £{min_p50:,.2f}, which is below your safety threshold of £{threshold:,.2f}.\n\n"
            f"• Root Cause: {driver}.\n"
            f"• Duration: Projected {danger_count} danger days within the next 30 days.\n"
            f"• Recommended Actions: Offer early settlement discounts on outstanding trade invoices or negotiate short payment tranches with suppliers before statutory VAT settlements."
        )

    def explain_recommendation(self, business: dict, action: dict, language: str = "en") -> str:
        title = action.get("title", "")
        cost = action.get("estimated_cost", 0.0)
        unlocked = action.get("cash_unlocked", 0.0)
        net = action.get("net_benefit", 0.0)

        return (
            f"Action Strategy: {title}. Implementing this unlocks £{unlocked:,.2f} in immediate working capital. "
            f"With an estimated execution cost of only £{cost:,.2f}, your net liquidity benefit is £{net:,.2f}."
        )

    def extract_invoice(self, raw_text: str) -> Dict[str, Any]:
        """
        Deterministic parser for invoice text/markdown/receipts (UK SME).
        """
        # Look for invoice number
        inv_num_match = re.search(r"\b(INV-[A-Z0-9\-_/]+)\b", raw_text, re.IGNORECASE)
        if not inv_num_match:
            inv_num_match = re.search(r"(?:invoice|bill)\s*(?:no|num|number|#)\s*[:#\-_]?\s*([A-Z0-9\-_/]+)", raw_text, re.IGNORECASE)
        inv_number = inv_num_match.group(1) if inv_num_match else f"INV-{os.urandom(2).hex().upper()}"

        # Look for total amount (supports £, GBP, INR, ₹)
        amt_match = re.search(r"(?:Total|Grand Total|Amount|Net Pay|£|GBP|₹|INR)[\s:Rs.]*([0-9,]+(?:\.[0-9]{2})?)", raw_text, re.IGNORECASE)
        if amt_match:
            try:
                amt_str = amt_match.group(1).replace(",", "")
                amount = float(amt_str)
            except ValueError:
                amount = 2500.0
        else:
            amount = 2500.0

        # Look for UK VAT number (e.g., GB123456789) or legacy GSTIN
        vat_match = re.search(r"\b(GB\s*[\d]{9}|[\d]{9})\b", raw_text, re.IGNORECASE)
        gstin_match = re.search(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b", raw_text)
        
        if vat_match:
            raw_vat = vat_match.group(1).replace(" ", "").upper()
            vat_number = raw_vat if raw_vat.startswith("GB") else f"GB{raw_vat}"
        elif gstin_match:
            vat_number = gstin_match.group(1)
        else:
            vat_number = "GB123456789"
        
        gstin = gstin_match.group(1) if gstin_match else vat_number

        # Look for dates
        date_match = re.findall(r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b", raw_text)
        issue_date = date_match[0] if len(date_match) > 0 else "2026-11-01"
        due_date = date_match[1] if len(date_match) > 1 else "2026-11-30"

        # Vendor name heuristic
        lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
        vendor_name = lines[0] if lines else "Travis Perkins Trade Supplies Ltd"

        return {
            "vendor_name": vendor_name,
            "invoice_number": inv_number,
            "amount": amount,
            "vat_number": vat_number,
            "gstin": gstin,
            "issue_date": issue_date,
            "due_date": due_date,
            "items_count": max(1, len(lines) - 3),
            "confidence_score": 0.94,
            "extracted_via": "mock_rules"
        }

class GeminiLLMProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.mock_fallback = MockLLMProvider()

    def _call_gemini(self, prompt: str) -> Optional[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return None

    def explain_cash_flow(self, business: dict, forecast: dict, language: str = "en") -> str:
        prompt = (
            f"You are CashLoop AI, a financial copilot.\n"
            f"Business: {business.get('name')}, Category: {business.get('category')}\n"
            f"Forecast Summary: Danger days={forecast.get('danger_days_count')}, "
            f"First danger date={forecast.get('first_danger_date')}, Shortfall={forecast.get('max_shortfall')}, "
            f"Primary driver={forecast.get('primary_driver')}.\n"
            f"Provide a concise, empathetic, high-clarity 3-paragraph explanation in English."
        )
        res = self._call_gemini(prompt)
        if res:
            return res.strip()
        return self.mock_fallback.explain_cash_flow(business, forecast, language)

    def explain_recommendation(self, business: dict, action: dict, language: str = "en") -> str:
        prompt = (
            f"Explain this costed cash-flow recommendation to a small business owner:\n"
            f"Action: {action.get('title')}\n"
            f"Cost: {action.get('estimated_cost')}, Cash Unlocked: {action.get('cash_unlocked')}, Net Benefit: {action.get('net_benefit')}.\n"
            f"Respond in English in 2 clear sentences."
        )
        res = self._call_gemini(prompt)
        if res:
            return res.strip()
        return self.mock_fallback.explain_recommendation(business, action, language)

    def extract_invoice(self, raw_text: str) -> Dict[str, Any]:
        prompt = (
            f"Extract structured invoice fields from the following text into valid JSON with keys: "
            f"'vendor_name', 'invoice_number', 'amount' (float), 'gstin', 'issue_date' (YYYY-MM-DD), 'due_date' (YYYY-MM-DD).\n"
            f"Invoice Text:\n{raw_text}\n"
            f"Output ONLY JSON."
        )
        res = self._call_gemini(prompt)
        if res:
            try:
                # clean json markdown
                cleaned = re.sub(r"^```json\s*|\s*```$", "", res.strip(), flags=re.MULTILINE)
                parsed = json.loads(cleaned)
                parsed["extracted_via"] = "gemini_live"
                return parsed
            except Exception:
                pass
        return self.mock_fallback.extract_invoice(raw_text)

def get_llm_service() -> LLMProvider:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return GeminiLLMProvider(api_key=api_key)
    return MockLLMProvider()
