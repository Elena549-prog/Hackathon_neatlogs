import type { EquityPoint } from "../events";

export interface SeriesPoint { time: string; value: number }

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Equity points -> chart series: valid dates only, finite values, ascending, last value wins per date. */
export function toSeries(points: EquityPoint[]): SeriesPoint[] {
  const byDate = new Map<string, number>();
  for (const [time, value] of points) {
    if (typeof time === "string" && DATE.test(time) && Number.isFinite(value)) byDate.set(time, value);
  }
  return [...byDate.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([time, value]) => ({ time, value }));
}
