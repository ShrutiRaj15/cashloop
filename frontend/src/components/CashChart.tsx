"use client";

import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Legend,
} from "recharts";
import { AlertTriangle, TrendingDown } from "lucide-react";

interface CashChartProps {
  data: Array<{
    date: string;
    day_number: number;
    balance_p10: number;
    balance_p50: number;
    balance_p90: number;
    naive_balance: number;
    min_cash_threshold: number;
    is_danger: boolean;
    shortfall: number;
  }>;
  minThreshold: number;
  selectedDate?: string | null;
  onSelectDate?: (date: string) => void;
}

export default function CashChart({
  data,
  minThreshold,
  selectedDate,
  onSelectDate,
}: CashChartProps) {
  if (!data || data.length === 0) {
    return <div className="h-72 flex items-center justify-center text-slate-400">Loading forecast...</div>;
  }

  // Format currency
  const formatINR = (val: number) => {
    return `₹${val.toLocaleString("en-IN")}`;
  };

  const chartData = data.map((d) => ({
    ...d,
    displayDate: d.date.slice(5), // MM-DD
    // For area chart band
    bandLower: d.balance_p10,
    bandWidth: Math.max(0, d.balance_p90 - d.balance_p10),
  }));

  const dangerDays = data.filter((d) => d.is_danger);

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2">
        <div>
          <h3 className="text-lg font-bold text-slate-900">
            30-Day Cash Position Forecast (p10/p50/p90)
          </h3>
          <p className="text-xs text-slate-500">
            Quantile regression forecasting with calendar and seasonal cycle features
          </p>
        </div>

        <div className="flex items-center space-x-4 text-xs font-medium">
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span>
            <span>Expected (p50)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-3 rounded-sm bg-emerald-100 border border-emerald-300 inline-block"></span>
            <span>Confidence Band [p10-p90]</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-0.5 border-t-2 border-dashed border-red-500 inline-block"></span>
            <span>Min Threshold</span>
          </div>
        </div>
      </div>

      {/* Danger Days Interactive Quick-Select Strip */}
      {dangerDays.length > 0 && (
        <div className="mt-4 p-3 bg-rose-50/80 rounded-xl border border-rose-200 flex flex-wrap items-center gap-2 text-xs">
          <span className="font-bold text-rose-800 flex items-center space-x-1">
            <AlertTriangle className="h-3.5 w-3.5 text-rose-600 inline" />
            <span>Danger Days (Click to inspect):</span>
          </span>
          {dangerDays.map((dd) => {
            const isSelected = selectedDate === dd.date;
            return (
              <button
                key={dd.date}
                onClick={() => onSelectDate && onSelectDate(dd.date)}
                className={`px-2.5 py-1 rounded-lg font-mono text-[11px] font-bold transition flex items-center space-x-1 ${
                  isSelected
                    ? "bg-rose-600 text-white shadow-sm ring-2 ring-rose-400"
                    : "bg-white text-rose-700 hover:bg-rose-100 border border-rose-200"
                }`}
              >
                <span>{dd.date}</span>
                <span className="text-[10px] opacity-80">(-{formatINR(dd.shortfall)})</span>
              </button>
            );
          })}
        </div>
      )}

      <div className="h-80 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="displayDate" tick={{ fontSize: 11, fill: "#64748b" }} />
            <YAxis
              tick={{ fontSize: 11, fill: "#64748b" }}
              tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(value: any, name: string) => {
                const labels: Record<string, string> = {
                  balance_p50: "Expected Balance (p50)",
                  balance_p10: "Lower Bound (p10)",
                  balance_p90: "Upper Bound (p90)",
                  naive_balance: "Naive 4-Wk Baseline",
                };
                return [formatINR(Number(value)), labels[name] || name];
              }}
              labelFormatter={(label) => `${"Date"}: 2026-${label}`}
              contentStyle={{
                backgroundColor: "#ffffff",
                borderColor: "#e2e8f0",
                borderRadius: "0.75rem",
                boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)",
                fontSize: "12px",
              }}
            />
            
            {/* Shaded Confidence Interval Band: Base (p10) stacked with (p90-p10) */}
            <Area
              type="monotone"
              dataKey="balance_p10"
              stackId="band"
              stroke="none"
              fill="transparent"
            />
            <Area
              type="monotone"
              dataKey="bandWidth"
              stackId="band"
              stroke="none"
              fill="#d1fae5"
              fillOpacity={0.65}
              name={"80% Confidence Interval"}
            />

            {/* Naive Baseline */}
            <Line
              type="monotone"
              dataKey="naive_balance"
              stroke="#94a3b8"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              dot={false}
              name="naive_balance"
            />

            {/* Expected Path (p50) */}
            <Line
              type="monotone"
              dataKey="balance_p50"
              stroke="#059669"
              strokeWidth={2.5}
              dot={{ r: 2.5, fill: "#059669" }}
              name="balance_p50"
            />

            {/* Minimum Safety Threshold */}
            <ReferenceLine
              y={minThreshold}
              stroke="#ef4444"
              strokeDasharray="5 5"
              strokeWidth={2}
              label={{
                value: `${"Min Threshold"} (${formatINR(minThreshold)})`,
                fill: "#dc2626",
                fontSize: 11,
                position: "insideTopLeft",
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
