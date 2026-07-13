// Shared formatting helpers for Freqtrade numeric values.

/** Fixed-decimal number, or an em dash for non-numbers. */
export function fmt(n: unknown, digits = 4): string {
  return typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";
}

/** A ratio (0.05) rendered as a percentage ("5.00%"). */
export function pct(n: unknown, digits = 2): string {
  return typeof n === "number" && Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : "—";
}

/** A signed amount ("+1.2340" / "-0.5000"), or an em dash. */
export function signed(n: unknown, digits = 4): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}`;
}
