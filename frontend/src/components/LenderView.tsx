"use client";

import React, { useState, useEffect } from "react";
import { Building2, AlertTriangle, ShieldCheck, ShieldAlert, TrendingDown, Users, Search, ArrowUpRight } from "lucide-react";

interface PortfolioSummary {
  total_msmes: number;
  total_exposure: number;
  total_projected_shortfall: number;
  critical_risk_count: number;
  warning_risk_count: number;
  safe_count: number;
  portfolio_health_index: number;
}

interface MSMEPortfolioItem {
  business_id: string;
  name: string;
  category: string;
  city: string;
  state: string;
  current_balance: number;
  min_cash_threshold: number;
  monthly_fixed_outflow: number;
  unbanked_cash_share_pct: number;
  risk_tier: "critical" | "warning" | "safe";
  health_score: number;
  days_to_danger?: number | null;
  projected_shortfall: number;
  primary_driver: string;
  has_drift: boolean;
  has_crunch_injected: boolean;
}

interface LenderViewProps {
  onSelectBusiness: (bizId: string) => void;
}

export default function LenderView({ onSelectBusiness }: LenderViewProps) {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [businesses, setBusinesses] = useState<MSMEPortfolioItem[]>([]);
  const [filterTier, setFilterTier] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const formatINR = (val: number) => `₹${val.toLocaleString("en-IN")}`;

  useEffect(() => {
    fetch("/api/lender/portfolio")
      .then((res) => res.json())
      .then((data) => {
        setSummary(data.portfolio_summary);
        setBusinesses(data.businesses);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load lender portfolio", err);
        setLoading(false);
      });
  }, []);

  if (loading || !summary) {
    return (
      <div className="h-96 flex items-center justify-center text-slate-400">
        Loading Lender Portfolio Early Warning Engine...
      </div>
    );
  }

  const filtered = businesses.filter((b) => {
    const matchesTier = filterTier === "all" || b.risk_tier === filterTier;
    const matchesSearch =
      b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      b.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      b.city.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTier && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-xl font-black text-slate-900 flex items-center space-x-2">
            <Building2 className="h-6 w-6 text-emerald-600" />
            <span>
              {"Lender & NBFC Portfolio Early-Warning Dashboard"}
            </span>
          </h2>
          <p className="text-xs text-slate-500">
            {"Real-time loan book distress prediction 3-6 weeks before default."}
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-500 font-medium">
            {"Portfolio Health Index:"}
          </span>
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
            {summary.portfolio_health_index}/100
          </span>
        </div>
      </div>

      {/* Aggregate Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">Total MSME Exposure</span>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {formatINR(summary.total_exposure)}
          </div>
          <span className="text-[10px] text-slate-500 mt-1 block">30 active credit lines</span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">Projected Shortfall (30d)</span>
          <div className="text-xl font-bold text-rose-600 mt-1">
            {formatINR(summary.total_projected_shortfall)}
          </div>
          <span className="text-[10px] text-rose-600/80 mt-1 block font-medium">Imminent liquidity gap</span>
        </div>

        <div className="bg-rose-50/70 rounded-2xl p-5 border border-rose-200 shadow-sm">
          <span className="text-[11px] text-rose-700 uppercase font-bold flex items-center space-x-1">
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>Critical Distress (&lt;14d)</span>
          </span>
          <div className="text-2xl font-black text-rose-700 mt-1">
            {summary.critical_risk_count} MSMEs
          </div>
          <span className="text-[10px] text-rose-600 block mt-1">High probability default</span>
        </div>

        <div className="bg-amber-50/70 rounded-2xl p-5 border border-amber-200 shadow-sm">
          <span className="text-[11px] text-amber-700 uppercase font-bold flex items-center space-x-1">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Warning (15-30d)</span>
          </span>
          <div className="text-2xl font-black text-amber-700 mt-1">
            {summary.warning_risk_count} MSMEs
          </div>
          <span className="text-[10px] text-amber-600 block mt-1">Shortfall projected</span>
        </div>

        <div className="bg-emerald-50/70 rounded-2xl p-5 border border-emerald-200 shadow-sm">
          <span className="text-[11px] text-emerald-700 uppercase font-bold flex items-center space-x-1">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Safe & Healthy</span>
          </span>
          <div className="text-2xl font-black text-emerald-700 mt-1">
            {summary.safe_count} MSMEs
          </div>
          <span className="text-[10px] text-emerald-600 block mt-1">Cushion above threshold</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-72">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder={"Filter by store, category, city..."}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          {["all", "critical", "warning", "safe"].map((tier) => (
            <button
              key={tier}
              onClick={() => setFilterTier(tier)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg capitalize transition ${
                filterTier === tier
                  ? "bg-slate-900 text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {tier}
            </button>
          ))}
        </div>
      </div>

      {/* Portfolio Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-400 uppercase tracking-wider text-[10px]">
                <th className="py-3 px-4">Business Name & Category</th>
                <th className="py-3 px-4">Location</th>
                <th className="py-3 px-4">Current Bank Bal</th>
                <th className="py-3 px-4">Risk Tier</th>
                <th className="py-3 px-4">Days to Danger</th>
                <th className="py-3 px-4">Projected Shortfall</th>
                <th className="py-3 px-4">Primary Driver</th>
                <th className="py-3 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((b) => (
                <tr key={b.business_id} className="hover:bg-slate-50/80 transition">
                  <td className="py-3.5 px-4">
                    <div className="font-bold text-slate-900">{b.name}</div>
                    <div className="text-[11px] text-slate-500 capitalize">
                      {b.category.replace(/_/g, " ")}
                      {b.has_crunch_injected && (
                        <span className="ml-1.5 px-1.5 py-0.2 bg-red-100 text-red-700 rounded text-[9px] font-bold">
                          Crunch Injected
                        </span>
                      )}
                      {b.has_drift && (
                        <span className="ml-1.5 px-1.5 py-0.2 bg-amber-100 text-amber-700 rounded text-[9px] font-bold">
                          Drift Detected
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-slate-600">
                    {b.city}, {b.state}
                  </td>
                  <td className="py-3.5 px-4 font-semibold text-slate-900">
                    {formatINR(b.current_balance)}
                  </td>
                  <td className="py-3.5 px-4">
                    {b.risk_tier === "critical" ? (
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300">
                        CRITICAL
                      </span>
                    ) : b.risk_tier === "warning" ? (
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                        WARNING
                      </span>
                    ) : (
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                        SAFE
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 font-bold">
                    {b.days_to_danger ? (
                      <span className="text-rose-600">{b.days_to_danger} days</span>
                    ) : (
                      <span className="text-slate-400">--</span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 font-bold text-slate-900">
                    {b.projected_shortfall > 0 ? (
                      <span className="text-rose-600">{formatINR(b.projected_shortfall)}</span>
                    ) : (
                      <span className="text-emerald-600">₹0</span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-slate-600 max-w-xs truncate" title={b.primary_driver}>
                    {b.primary_driver}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <button
                      onClick={() => onSelectBusiness(b.business_id)}
                      className="inline-flex items-center space-x-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 transition"
                    >
                      <span>Inspect</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
