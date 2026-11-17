"use client";

import React from "react";
import { FileText, Clock, AlertTriangle, CheckCircle, UserCheck } from "lucide-react";

interface InvoiceItem {
  id: string;
  invoice_number: string;
  customer_name: string;
  customer_habit: string;
  amount: number;
  issue_date: string;
  due_date: string;
  paid_date?: string | null;
  status: string;
  expected_payment_date?: string | null;
  delay_p50?: number | null;
}

interface InvoicesListProps {
  invoices: InvoiceItem[];
  onOpenExtractModal?: () => void;
}

export default function InvoicesList({ invoices, onOpenExtractModal }: InvoicesListProps) {
  const formatINR = (val: number) => `₹${val.toLocaleString("en-IN")}`;

  const openInvoices = invoices.filter((i) => i.status !== "paid");

  const getHabitBadge = (habit: string) => {
    switch (habit) {
      case "disciplined":
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-emerald-100 text-emerald-800">
            {"Disciplined (0-3d)"}
          </span>
        );
      case "chronic_late":
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-rose-100 text-rose-800">
            {"Chronic Delay (+21d)"}
          </span>
        );
      case "erratic":
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-amber-100 text-amber-800">
            {"Erratic Payer"}
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-slate-100 text-slate-700">
            {"Seasonal"}
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div>
          <h3 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
            <FileText className="h-5 w-5 text-indigo-600" />
            <span>
              {"Open Invoices & Payment Behavior Model"}
            </span>
          </h3>
          <p className="text-xs text-slate-500">
            {"Customer-specific quantile delay distributions mapped directly into cash flow forecasts."}
          </p>
        </div>

        {onOpenExtractModal && (
          <button
            onClick={onOpenExtractModal}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition"
          >
            {"+ Extract / Scan Invoice"}
          </button>
        )}
      </div>

      <div className="overflow-x-auto mt-4">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-slate-400 uppercase tracking-wider text-[10px]">
              <th className="py-2.5 px-3">{"Invoice #"}</th>
              <th className="py-2.5 px-3">{"Customer"}</th>
              <th className="py-2.5 px-3">{"Payment Habit"}</th>
              <th className="py-2.5 px-3">{"Due Date"}</th>
              <th className="py-2.5 px-3">{"Predicted Pay Date"}</th>
              <th className="py-2.5 px-3 text-right">{"Amount"}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {openInvoices.slice(0, 7).map((inv) => (
              <tr key={inv.id} className="hover:bg-slate-50 transition">
                <td className="py-3 px-3 font-semibold text-slate-900">{inv.invoice_number}</td>
                <td className="py-3 px-3 text-slate-700">{inv.customer_name}</td>
                <td className="py-3 px-3">{getHabitBadge(inv.customer_habit)}</td>
                <td className="py-3 px-3 text-slate-500">{inv.due_date}</td>
                <td className="py-3 px-3 font-medium text-indigo-700">
                  {inv.expected_payment_date ? (
                    <span className="flex items-center space-x-1">
                      <Clock className="h-3 w-3 text-indigo-500 inline" />
                      <span>{inv.expected_payment_date}</span>
                      {inv.delay_p50 && inv.delay_p50 > 0 ? (
                        <span className="text-[10px] text-amber-600 font-bold">
                          (+{inv.delay_p50}d)
                        </span>
                      ) : null}
                    </span>
                  ) : (
                    "On time"
                  )}
                </td>
                <td className="py-3 px-3 text-right font-bold text-slate-900">
                  {formatINR(inv.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
