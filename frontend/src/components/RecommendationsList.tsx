"use client";

import React, { useState } from "react";
import { CheckCircle2, DollarSign, Clock, ArrowRight, Zap, Check, AlertCircle } from "lucide-react";

interface Action {
  id: string;
  action_type: string;
  title: string;
  description?: string;
  description_en?: string;
  estimated_cost: number;
  cash_unlocked: number;
  net_benefit: number;
  status: string;
}

interface RecommendationsListProps {
  recommendations: Action[];
  onActionStatusChange?: (actionId: string, status: string) => void;
}

export default function RecommendationsList({
  recommendations,
  onActionStatusChange,
}: RecommendationsListProps) {
  const [actionStates, setActionStates] = useState<Record<string, string>>({});
  const [appliedNotification, setAppliedNotification] = useState<string | null>(null);

  const formatINR = (val: number) => `₹${val.toLocaleString("en-IN")}`;

  const handleAction = async (actionId: string, status: "accepted" | "rejected") => {
    setActionStates((prev) => ({ ...prev, [actionId]: status }));
    try {
      await fetch(`/api/actions/${actionId}/record`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (status === "accepted") {
        setAppliedNotification(actionId);
        setTimeout(() => setAppliedNotification(null), 4000);
      }
      if (onActionStatusChange) {
        onActionStatusChange(actionId, status);
      }
    } catch (e) {
      console.error("Failed to record action", e);
    }
  };

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="bg-white rounded-2xl p-6 border border-slate-200 text-center">
        <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto mb-2" />
        <h4 className="font-bold text-slate-800">
          No Urgent Actions Required
        </h4>
        <p className="text-xs text-slate-500 mt-1">
          Your projected balances remain above your safety threshold.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
            <Zap className="h-5 w-5 text-amber-500" />
            <span>
              Recommended Costed Interventions
            </span>
          </h3>
          <p className="text-xs text-slate-500">
            Algorithmically ranked strategies to avert projected shortfall with net positive liquidity.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {recommendations.map((rec) => {
          const currentStatus = actionStates[rec.id] || rec.status || "proposed";
          const isAccepted = currentStatus === "accepted" || currentStatus === "executed";
          const isRejected = currentStatus === "rejected";

          return (
            <div
              key={rec.id}
              className={`rounded-2xl p-5 border transition flex flex-col justify-between ${
                isAccepted
                  ? "bg-emerald-50/70 border-emerald-300 ring-2 ring-emerald-500/20"
                  : isRejected
                  ? "bg-slate-50 border-slate-200 opacity-60"
                  : "bg-white border-slate-200 hover:border-slate-300 shadow-sm"
              }`}
            >
              <div>
                {/* Header Tag */}
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                    {rec.action_type.replace(/_/g, " ")}
                  </span>
                  {isAccepted && (
                    <span className="flex items-center space-x-1 text-xs font-semibold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                      <Check className="h-3 w-3" />
                      <span>Applied</span>
                    </span>
                  )}
                </div>

                {/* Title */}
                <h4 className="font-bold text-sm text-slate-900 mb-2 leading-snug">
                  {rec.title}
                </h4>

                {/* Description */}
                <p className="text-xs text-slate-600 mb-4 leading-relaxed">
                  {rec.description || rec.description_en}
                </p>

                {/* Financial Impact Metric Pill */}
                <div className="grid grid-cols-3 gap-2 bg-slate-50 rounded-xl p-3 border border-slate-100 mb-4 text-center">
                  <div>
                    <span className="block text-[10px] text-slate-400 uppercase">
                      Est. Cost
                    </span>
                    <span className="text-xs font-bold text-slate-700">
                      {formatINR(rec.estimated_cost)}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-emerald-600 font-semibold uppercase">
                      Cash Unlocked
                    </span>
                    <span className="text-xs font-bold text-emerald-700">
                      {formatINR(rec.cash_unlocked)}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-slate-400 uppercase">
                      Net Benefit
                    </span>
                    <span className="text-xs font-bold text-slate-900">
                      {formatINR(rec.net_benefit)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2 pt-2 border-t border-slate-100">
                {!isAccepted && !isRejected ? (
                  <>
                    <button
                      onClick={() => handleAction(rec.id, "accepted")}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs py-2 px-3 rounded-lg shadow-sm transition flex items-center justify-center space-x-1"
                    >
                      <span>Accept Action</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => handleAction(rec.id, "rejected")}
                      className="text-slate-400 hover:text-slate-600 text-xs py-2 px-2.5 rounded-lg border border-slate-200 transition"
                    >
                      Dismiss
                    </button>
                  </>
                ) : isAccepted ? (
                  <div className="w-full text-center py-1 text-xs text-emerald-700 font-medium">
                    Closed-loop feedback logged. Outcome tracking active.
                  </div>
                ) : (
                  <div className="w-full text-center py-1 text-xs text-slate-400">
                    Dismissed
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
