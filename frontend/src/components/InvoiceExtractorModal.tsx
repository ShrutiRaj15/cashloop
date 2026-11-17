"use client";

import React, { useState } from "react";
import { X, Sparkles, Upload, FileCode, CheckCircle, ArrowRight } from "lucide-react";

interface InvoiceExtractorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SAMPLE_INVOICES = {
  kirana: `Sharma Kirana Supplies
Main Market Road, Indore, MP
GSTIN: 23AABCS1234H1Z5
Bill No: INV-2026-9812
Date: 2026-11-04
Due Date: 2026-11-25
Item 1: Premium Basmati Rice 50kg x 10 - Rs. 40,000
Item 2: Refined Oil Tins x 15 - Rs. 32,500
Total Amount: INR 72,500.00
Payment Terms: 21 Days Credit`,
  textile: `Vardhman Fabrics & Textile Wholesalers
Ring Road Textile Market, Surat, Gujarat
GSTIN: 24AAACV1234F1Z8
Invoice No: INV-SURAT-4482
Date: 2026-11-02
Due Date: 2026-12-02
Description: Designer Silk & Chiffon Sarees (Lot #402)
Total Amount: INR 1,85,000.00
Bank Settlement Terms: Net 30`
};

export default function InvoiceExtractorModal({ isOpen, onClose }: InvoiceExtractorModalProps) {
  const [inputText, setInputText] = useState(SAMPLE_INVOICES.kirana);
  const [loading, setLoading] = useState(false);
  const [extractedData, setExtractedData] = useState<any>(null);

  if (!isOpen) return null;

  const handleExtract = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/invoices/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: inputText }),
      });
      const data = await res.json();
      setExtractedData(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95">
        <div className="flex items-center justify-between p-5 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center space-x-2">
            <div className="h-8 w-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">
                {"AI Invoice Extractor (Mock / Gemini)"}
              </h3>
              <p className="text-[11px] text-slate-500">
                {"Extract entities & automatically map to customer payment delay forecasts"}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Preset Buttons */}
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400 font-medium">
              {"Load Sample:"}
            </span>
            <button
              onClick={() => { setInputText(SAMPLE_INVOICES.kirana); setExtractedData(null); }}
              className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition"
            >
              Kirana Stock Bill
            </button>
            <button
              onClick={() => { setInputText(SAMPLE_INVOICES.textile); setExtractedData(null); }}
              className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition"
            >
              Textile Wholesaler Bill
            </button>
          </div>

          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            rows={5}
            className="w-full text-xs font-mono p-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="Paste raw invoice text or OCR output here..."
          />

          <button
            onClick={handleExtract}
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-2.5 rounded-xl shadow-sm transition flex items-center justify-center space-x-2"
          >
            {loading ? (
              <span>Extracting...</span>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                <span>{"Run AI Extraction"}</span>
              </>
            )}
          </button>

          {/* Result Card */}
          {extractedData && (
            <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-4 text-xs space-y-3">
              <div className="flex items-center justify-between text-emerald-800 font-bold border-b border-emerald-200/60 pb-2">
                <span className="flex items-center space-x-1.5">
                  <CheckCircle className="h-4 w-4 text-emerald-600" />
                  <span>{"Successfully Parsed Entity"}</span>
                </span>
                <span className="text-[10px] uppercase tracking-wider bg-emerald-100 px-2 py-0.5 rounded-full text-emerald-700">
                  {extractedData.extracted_via}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-slate-700">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Vendor</span>
                  <span className="font-semibold">{extractedData.vendor_name}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Invoice #</span>
                  <span className="font-semibold">{extractedData.invoice_number}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">GSTIN</span>
                  <span className="font-mono text-[11px]">{extractedData.gstin}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Amount</span>
                  <span className="font-bold text-emerald-700 text-sm">
                    ₹{Number(extractedData.amount).toLocaleString("en-IN")}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Due Date</span>
                  <span>{extractedData.due_date}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Confidence</span>
                  <span>{(extractedData.confidence_score * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
