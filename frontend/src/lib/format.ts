// Shared formatting helpers for Freqtrade numeric values.

/** Fixed-decimal number, or an em dash for non-numbers. */
export function fmt(n: unknown, digits = 4): string {
  return typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";
}

/** A ratio (0.05) rendered as a percentage ("5.00%"). */
export function pct(n: unknown, digits = 2): string {
  return typeof n === "number" && Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : "—";
}

/** An exchange rate. Sub-1 prices (e.g. SHIB) need more decimals than large ones (e.g. BTC). */
export function price(n: unknown): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return n.toFixed(Math.abs(n) >= 1 ? 4 : 8);
}

/** A signed amount ("+1.2340" / "-0.5000"), or an em dash. */
export function signed(n: unknown, digits = 4): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}`;
}
