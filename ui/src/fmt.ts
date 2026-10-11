// Number formatting for the mono figures. Returns are fractions (0.012 = 1.2%).
export const pct = (x: number | undefined | null, digits = 2): string =>
  typeof x === "number" && Number.isFinite(x) ? `${x > 0 ? "+" : ""}${(x * 100).toFixed(digits)}%` : "–";
export const int = (n: number | undefined | null): string =>
  typeof n === "number" && Number.isFinite(n) ? Math.round(n).toLocaleString("en-US") : "–";
export const usd = (x: number): string => `$${x.toFixed(4)}`;
