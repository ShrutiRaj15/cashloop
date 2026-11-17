"use client";

import React from "react";
import { Activity, ShieldAlert, Store, Building2, Globe, Sparkles } from "lucide-react";

interface NavbarProps {
  currentView: "msme" | "lender" | "loops";
  setCurrentView: (view: "msme" | "lender" | "loops") => void;
  businesses: Array<{ id: string; name: string; category: string }>;
  selectedBizId: string;
  setSelectedBizId: (id: string) => void;
}

export default function Navbar({
  currentView,
  setCurrentView,
  businesses,
  selectedBizId,
  setSelectedBizId,
}: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
            <Activity className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xl font-bold tracking-tight text-slate-900">CashLoop</span>
              <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                Closed-Loop v1.0
              </span>
            </div>
            <p className="text-xs text-slate-500 hidden sm:block">
              Cash-Flow Early-Warning System for MSMEs
            </p>
          </div>
        </div>

        {/* View Switcher */}
        <div className="flex items-center space-x-3">
          {/* Business Selector (for MSME and Loops view) */}
          {currentView !== "lender" && (
            <div className="hidden md:flex items-center space-x-2">
              <Store className="h-4 w-4 text-slate-400" />
              <select
                value={selectedBizId}
                onChange={(e) => setSelectedBizId(e.target.value)}
                className="text-sm font-medium bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                {businesses.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.category.replace(/_/g, " ")})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Three-Way View Toggle */}
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => setCurrentView("msme")}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-semibold transition ${
                currentView === "msme"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Store className="h-3.5 w-3.5" />
              <span>Shop Owner</span>
            </button>
            <button
              onClick={() => setCurrentView("lender")}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-semibold transition ${
                currentView === "lender"
                  ? "bg-white text-emerald-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Building2 className="h-3.5 w-3.5" />
              <span>Lender</span>
            </button>
            <button
              onClick={() => setCurrentView("loops")}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-semibold transition ${
                currentView === "loops"
                  ? "bg-white text-indigo-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Loop Engine</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
