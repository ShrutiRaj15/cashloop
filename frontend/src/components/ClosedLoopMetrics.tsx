"use client";

import React from "react";
import { RefreshCw, AlertOctagon } from "lucide-react";

interface ClosedLoopData {
  business_id: string;
  total_evaluations: number;
  overall_wape: number;
  interval_coverage_pct: number;
  drift_retrains_triggered: number;
  total_recommendations: number;
  actions_averted: number;
  actions_mitigated: number;
  action_success_rate_pct: number;
  drift_events?: Array<{
    id: string;
    event_date: string;
    rolling_wape_before: number;
    reason: string;
  }>;
}

interface ClosedLoopMetricsProps {
  data: ClosedLoopData | null;
}

export default function ClosedLoopMetrics({ data }: ClosedLoopMetricsProps) {
  if (!data) return null;

  const notSimulated = data.total_evaluations === 0;

  return (
    <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-md border border-slate-800">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 border-b border-slate-800 gap-2">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <RefreshCw className="h-5 w-5 animate-spin-slow" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white flex items-center space-x-2">
              <span>Closed-Loop Learning &amp; Self-Correction Engine</span>
              <span className="text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                Active Feedback
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Predict -&gt; Compare with Actuals -&gt; Measure Error -&gt; Recalibrate -&gt; Track Advice
            </p>
          </div>
        </div>
      </div>

      {notSimulated && (
        <div className="mt-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs px-3 py-2">
          Simulation has not been run for this business yet, so no learning metrics are available.
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5">
        <div className="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">
            Forecast WAPE
          </span>
          <div className="text-2xl font-black text-emerald-400 mt-1">
            {notSimulated ? "—" : `${(data.overall_wape * 100).toFixed(1)}%`}
          </div>
          <span className="text-[10px] text-emerald-400/80 font-medium mt-1 block">
            {`Based on ${data.total_evaluations} evaluated predictions`}
          </span>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">
            Drift Auto-Retrains
          </span>
          <div className="text-2xl font-black text-amber-400 mt-1">
            {data.drift_retrains_triggered}
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">
            Triggered on concept shifts
          </span>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">
            Action Success Rate
          </span>
          <div className="text-2xl font-black text-cyan-400 mt-1">
            {data.total_recommendations === 0 ? "—" : `${data.action_success_rate_pct}%`}
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">
            {data.actions_averted} crunches averted
          </span>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">
            Interval Coverage [p10,p90]
          </span>
          <div className="text-2xl font-black text-violet-400 mt-1">
            {notSimulated ? "—" : `${data.interval_coverage_pct}%`}
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">
            Target: 80% coverage
          </span>
        </div>
      </div>

      {/* Drift Events Breakdown if present */}
      {data.drift_events && data.drift_events.length > 0 && (
        <div className="mt-5 pt-4 border-t border-slate-800 text-xs">
          <span className="text-slate-400 font-semibold block mb-2">
            Recent Drift Alerts &amp; Autonomous Recalibrations:
          </span>
          <div className="space-y-1.5">
            {data.drift_events.map((d) => (
              <div
                key={d.id}
                className="flex items-center justify-between bg-slate-800/40 px-3 py-1.5 rounded-lg text-slate-300"
              >
                <div className="flex items-center space-x-2">
                  <AlertOctagon className="h-3.5 w-3.5 text-amber-400" />
                  <span>{d.reason}</span>
                </div>
                <span className="text-slate-500 text-[10px]">{d.event_date}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}