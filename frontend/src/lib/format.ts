/**
 * Central UK currency and date formatting utilities for CashLoop.
 * Locale: en-GB, Currency: GBP (£)
 */

export function formatMoney(val: number | null | undefined, decimals: number = 0): string {
  if (val === null || val === undefined || isNaN(val)) {
    return "£0";
  }
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val);
}

export function formatShortMoney(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) {
    return "£0";
  }
  const absVal = Math.abs(val);
  const sign = val < 0 ? "-" : "";
  if (absVal >= 1_000_000) {
    return `${sign}£${(absVal / 1_000_000).toFixed(1)}m`;
  }
  if (absVal >= 1_000) {
    return `${sign}£${(absVal / 1_000).toFixed(0)}k`;
  }
  return `${sign}£${absVal.toFixed(0)}`;
}

export function formatDate(dateStr: string | Date | null | undefined): string {
  if (!dateStr) return "-";
  const d = typeof dateStr === "string" ? new Date(dateStr) : dateStr;
  if (isNaN(d.getTime())) return String(dateStr);
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(d);
}

export function formatPercent(val: number | null | undefined, decimals: number = 1): string {
  if (val === null || val === undefined || isNaN(val)) {
    return "0.0%";
  }
  return `${val.toFixed(decimals)}%`;
}
