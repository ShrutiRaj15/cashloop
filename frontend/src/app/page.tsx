"use client";

import React, { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import CashChart from "@/components/CashChart";
import RecommendationsList from "@/components/RecommendationsList";
import InvoicesList from "@/components/InvoicesList";
import ClosedLoopMetrics from "@/components/ClosedLoopMetrics";
import InvoiceExtractorModal from "@/components/InvoiceExtractorModal";
import LenderView from "@/components/LenderView";
import LoopDashboardView from "@/components/LoopDashboardView";
import {
  AlertTriangle,
  ShieldAlert,
  Wallet,
  Building2,
  TrendingDown,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  FileText,
  BadgeAlert,
  Upload,
  Calendar,
  CheckCircle,
  HelpCircle
} from "lucide-react";

export default function Home() {
  const [currentView, setCurrentView] = useState<"msme" | "lender" | "loops">("msme");
  const [businesses, setBusinesses] = useState<any[]>([]);
  const [selectedBizId, setSelectedBizId] = useState<string>("biz_001");
  const [business, setBusiness] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [closedLoopData, setClosedLoopData] = useState<any>(null);
  const [explanation, setExplanation] = useState<string>("");
  const [isExtractModalOpen, setIsExtractModalOpen] = useState(false);
  const [selectedDangerDate, setSelectedDangerDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Statement upload state
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const formatINR = (val: number) => `₹${val.toLocaleString("en-IN")}`;

  // Fetch businesses list on mount
  useEffect(() => {
    fetch("/api/businesses")
      .then((res) => res.json())
      .then((data) => {
        setBusinesses(data);
        if (data.length > 0 && !selectedBizId) {
          setSelectedBizId(data[0].id);
        }
      })
      .catch((err) => console.error("Error loading businesses", err));
  }, []);

  // Refresh all business data
  const refreshBusinessData = (bizId: string) => {
    setLoading(true);
    Promise.all([
      fetch(`/api/businesses/${bizId}`).then((r) => r.json()),
      fetch(`/api/forecasts/${bizId}`).then((r) => r.json()),
      fetch(`/api/invoices/${bizId}`).then((r) => r.json()),
      fetch(`/api/closed-loop/${bizId}`).then((r) => r.json()),
    ])
      .then(([bizData, forecastData, invoiceData, loopData]) => {
        setBusiness(bizData);
        setForecast(forecastData);
        setInvoices(invoiceData);
        setClosedLoopData(loopData);
        if (forecastData.first_danger_date) {
          setSelectedDangerDate(forecastData.first_danger_date);
        } else {
          setSelectedDangerDate(null);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error loading MSME details", err);
        setLoading(false);
      });
  };

  // Fetch data when selectedBizId changes
  useEffect(() => {
    if (!selectedBizId) return;
    refreshBusinessData(selectedBizId);
  }, [selectedBizId]);

  // Fetch explanation when business changes
  useEffect(() => {
    if (!selectedBizId) return;
    fetch(`/api/explanations/${selectedBizId}`)
      .then((r) => r.json())
      .then((data) => setExplanation(data.explanation))
      .catch((err) => console.error("Error loading explanation", err));
  }, [selectedBizId]);

  const handleSelectBusinessFromLender = (bizId: string) => {
    setSelectedBizId(bizId);
    setCurrentView("msme");
  };

  // CSV Statement Upload handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadLoading(true);
    setUploadSuccess(null);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("business_id", selectedBizId);

    try {
      const res = await fetch("/api/statements/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      setUploadSuccess(
        `Successfully imported ${data.transactions_imported} transactions! New Balance: ${formatINR(data.new_balance)}`
      );
      // Refresh state
      refreshBusinessData(selectedBizId);
    } catch (err: any) {
      setUploadError(err.message || "Failed to process bank statement");
    } finally {
      setUploadLoading(false);
      e.target.value = "";
    }
  };

  // Create demo CSV on the fly for testing
  const handleUploadSampleStatement = async () => {
    setUploadLoading(true);
    setUploadSuccess(null);
    setUploadError(null);

    const sampleCsv = `date,description,amount,type
2026-11-06,Customer payment UPI,45000,credit
2026-11-07,Local store sale cash deposit,18500,credit
2026-11-08,Packaging supplies wholesale,12000,debit
2026-11-09,Electricity and utility bill,8400,debit`;

    const blob = new Blob([sampleCsv], { type: "text/csv" });
    const file = new File([blob], "sample_statement_nov2026.csv", { type: "text/csv" });

    const formData = new FormData();
    formData.append("file", file);
    formData.append("business_id", selectedBizId);

    try {
      const res = await fetch("/api/statements/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");

      setUploadSuccess(
        `Sample statement imported! ${data.transactions_imported} txns recorded. New Balance: ${formatINR(data.new_balance)}`
      );
      refreshBusinessData(selectedBizId);
    } catch (err: any) {
      setUploadError(err.message || "Failed to process sample bank statement");
    } finally {
      setUploadLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar
        currentView={currentView}
        setCurrentView={setCurrentView}
        businesses={businesses}
        selectedBizId={selectedBizId}
        setSelectedBizId={setSelectedBizId}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {currentView === "lender" ? (
          <LenderView onSelectBusiness={handleSelectBusinessFromLender} />
        ) : currentView === "loops" ? (
          <LoopDashboardView businessId={selectedBizId} />
        ) : loading || !business || !forecast ? (
          <div className="h-96 flex flex-col items-center justify-center space-y-3 text-slate-400">
            <RefreshCw className="h-8 w-8 animate-spin text-emerald-600" />
            <span className="text-sm font-medium">Loading CashLoop Intelligence...</span>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Top MSME Header Banner */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <h1 className="text-xl font-black text-slate-900">{business.name}</h1>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 capitalize border border-slate-200">
                    {business.category.replace(/_/g, " ")}
                  </span>
                  {business.has_crunch_injected && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-700 border border-rose-300">
                      Stress Crunch Injected
                    </span>
                  )}
                  {business.has_drift && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-300">
                      Concept Drift Shift
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {business.city}, {business.state} • GSTIN: <span className="font-mono text-slate-700">{business.gstin}</span>
                </p>
              </div>

              {/* Status Badges & Trust Score */}
              <div className="flex flex-wrap items-center gap-3">
                {/* Rolling Trust Score Badge */}
                <div className="flex items-center space-x-1.5 bg-emerald-50 border border-emerald-200 text-emerald-800 px-3 py-1.5 rounded-xl text-xs font-bold shadow-xs">
                  <CheckCircle className="h-4 w-4 text-emerald-600" />
                  <span>Trust Score: {closedLoopData?.forecast_trust_score ?? 92}/100</span>
                </div>

                {forecast.danger_days_count > 0 ? (
                  <div className="flex items-center space-x-2 bg-rose-50 border border-rose-200 text-rose-800 px-3 py-1.5 rounded-xl text-xs font-bold animate-pulse">
                    <ShieldAlert className="h-4 w-4 text-rose-600" />
                    <span>
                      {`${forecast.danger_days_count} Danger Days Detected`}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2 bg-emerald-50 border border-emerald-200 text-emerald-800 px-3 py-1.5 rounded-xl text-xs font-bold">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    <span>Cash Position Safe</span>
                  </div>
                )}
              </div>
            </div>

            {/* Financial Health Metrics Strip */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
                <span className="text-[11px] text-slate-400 uppercase font-semibold block">
                  Current Bank Balance
                </span>
                <div className="text-xl font-black text-slate-900 mt-1">
                  {formatINR(business.current_balance)}
                </div>
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  {business.unbanked_cash_share * 100}% Cash unbanked
                </span>
              </div>

              <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
                <span className="text-[11px] text-slate-400 uppercase font-semibold block">
                  Min Safety Threshold
                </span>
                <div className="text-xl font-black text-slate-700 mt-1">
                  {formatINR(business.min_cash_threshold)}
                </div>
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  Buffer floor
                </span>
              </div>

              <div className={`rounded-2xl p-5 border shadow-sm ${
                forecast.min_projected_balance_p50 < business.min_cash_threshold
                  ? "bg-rose-50/70 border-rose-200"
                  : "bg-white border-slate-200"
              }`}>
                <span className={`text-[11px] uppercase font-semibold block ${
                  forecast.min_projected_balance_p50 < business.min_cash_threshold ? "text-rose-700" : "text-slate-400"
                }`}>
                  30-Day Lowest Dip (p50)
                </span>
                <div className={`text-xl font-black mt-1 ${
                  forecast.min_projected_balance_p50 < business.min_cash_threshold ? "text-rose-700" : "text-emerald-700"
                }`}>
                  {formatINR(forecast.min_projected_balance_p50)}
                </div>
                <span className="text-[10px] text-slate-500 mt-0.5 block">
                  p10: {formatINR(forecast.min_projected_balance_p10)}
                </span>
              </div>

              <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
                <span className="text-[11px] text-slate-400 uppercase font-semibold block">
                  Max Projected Deficit
                </span>
                <div className={`text-xl font-black mt-1 ${
                  forecast.max_shortfall > 0 ? "text-rose-600" : "text-emerald-600"
                }`}>
                  {forecast.max_shortfall > 0 ? formatINR(forecast.max_shortfall) : "₹0"}
                </div>
                <span className="text-[10px] text-slate-500 mt-0.5 block">
                  {forecast.first_danger_date
                    ? `Due ${forecast.first_danger_date}`
                    : "No deficit projected"}
                </span>
              </div>
            </div>

            {/* AI Plain-Language Early-Warning Explanation Banner */}
            {explanation && (
              <div className={`rounded-2xl p-5 border shadow-sm ${
                forecast.danger_days_count > 0
                  ? "bg-gradient-to-r from-rose-50 via-amber-50 to-orange-50 border-amber-200"
                  : "bg-gradient-to-r from-emerald-50 via-teal-50 to-cyan-50 border-emerald-200"
              }`}>
                <div className="flex items-start space-x-3">
                  <div className={`p-2 rounded-xl mt-0.5 ${
                    forecast.danger_days_count > 0 ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
                  }`}>
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-sm text-slate-900">
                        CashLoop AI Intelligence Brief
                      </h4>
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        Automated Copilot
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 mt-2 leading-relaxed whitespace-pre-line font-medium">
                      {explanation}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Bank Statement CSV Ingestion Box */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex items-center space-x-3">
                <div className="h-10 w-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                  <Upload className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-slate-900">
                    Upload Bank Statement (CSV)
                  </h4>
                  <p className="text-xs text-slate-500">
                    Ingest actual banking transactions to automatically recalibrate liquidity models.
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3 w-full md:w-auto">
                <label className="cursor-pointer bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold py-2 px-3.5 rounded-xl transition flex items-center space-x-1.5 shadow-sm">
                  <Upload className="h-3.5 w-3.5" />
                  <span>{uploadLoading ? "Uploading..." : "Upload CSV"}</span>
                  <input
                    type="file"
                    accept=".csv,.txt"
                    onChange={handleFileUpload}
                    disabled={uploadLoading}
                    className="hidden"
                  />
                </label>

                <button
                  onClick={handleUploadSampleStatement}
                  disabled={uploadLoading}
                  className="bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium py-2 px-3 rounded-xl transition"
                >
                  {uploadLoading ? "Processing..." : "Use Sample CSV"}
                </button>
              </div>
            </div>

            {/* Upload Feedback Alerts */}
            {uploadSuccess && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center space-x-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span>{uploadSuccess}</span>
              </div>
            )}
            {uploadError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center space-x-2">
                <AlertTriangle className="h-4 w-4 text-rose-600" />
                <span>{uploadError}</span>
              </div>
            )}

            {/* Main Interactive Forecast Chart with Danger Day Selector */}
            <CashChart
              data={forecast.daily_forecasts}
              minThreshold={business.min_cash_threshold}
              selectedDate={selectedDangerDate}
              onSelectDate={(date) => setSelectedDangerDate(date)}
            />

            {/* Selected Danger Day Drilldown Breakdown Card */}
            {selectedDangerDate && (
              <div className="bg-rose-50/70 border border-rose-200 rounded-2xl p-5">
                <div className="flex items-center justify-between pb-3 border-b border-rose-200/60">
                  <div className="flex items-center space-x-2">
                    <ShieldAlert className="h-5 w-5 text-rose-600" />
                    <h4 className="font-bold text-sm text-rose-900">
                      Danger Day Deep-Dive: {selectedDangerDate}
                    </h4>
                  </div>
                  <span className="text-[10px] font-bold uppercase bg-rose-200/70 text-rose-800 px-2 py-0.5 rounded-full">
                    Crunch Alert
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 text-xs">
                  <div className="bg-white p-3.5 rounded-xl border border-rose-100">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">
                      Projected Balance
                    </span>
                    <span className="text-base font-black text-rose-700 mt-1 block">
                      {formatINR(
                        forecast.daily_forecasts.find((d: any) => d.date === selectedDangerDate)?.balance_p50 || 0
                      )}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      Floor threshold: {formatINR(business.min_cash_threshold)}
                    </span>
                  </div>

                  <div className="bg-white p-3.5 rounded-xl border border-rose-100">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">
                      Projected Shortfall
                    </span>
                    <span className="text-base font-black text-rose-600 mt-1 block">
                      {formatINR(
                        forecast.daily_forecasts.find((d: any) => d.date === selectedDangerDate)?.shortfall || 0
                      )}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      Below mandatory safety cushion
                    </span>
                  </div>

                  <div className="bg-white p-3.5 rounded-xl border border-rose-100">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">
                      Primary Driver
                    </span>
                    <span className="text-xs font-semibold text-slate-800 mt-1 block">
                      {selectedDangerDate.endsWith("-20")
                        ? "Monthly Statutory Outflow"
                        : selectedDangerDate.endsWith("-05")
                        ? "Employee Salary Outflow Cycle"
                        : "Customer delayed payment settlement"}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      Recommended: See action interventions below
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Costed Recommendations */}
            <RecommendationsList
              recommendations={forecast.recommendations}
              onActionStatusChange={() => {
                // Refresh closed loop status
                fetch(`/api/closed-loop/${selectedBizId}`)
                  .then((r) => r.json())
                  .then((d) => setClosedLoopData(d));
              }}
            />

            {/* Open Invoices & Customer Payment Behavior */}
            <InvoicesList
              invoices={invoices}
              onOpenExtractModal={() => setIsExtractModalOpen(true)}
            />

            {/* Closed-Loop Learning & Self-Correction Scorecard */}
            <ClosedLoopMetrics data={closedLoopData} />
          </div>
        )}
      </main>

      {/* Invoice OCR Extractor Modal */}
      <InvoiceExtractorModal
        isOpen={isExtractModalOpen}
        onClose={() => setIsExtractModalOpen(false)}
      />
    </div>
  );
}
