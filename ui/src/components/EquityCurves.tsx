// Evidence panel: train and validation equity curves (lightweight-charts), the stats legend from the
// backtest_result event, and a baseline strip. Curves draw in over 600 ms when a result arrives.
import { ColorType, LineSeries, createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { EquityPoint, Stats } from "../events";
import { int, pct } from "../fmt";
import type { UiState } from "../state";
import { toSeries } from "./equitySeries";

const COLORS = { panel: "#11161e", line: "#1f2733", muted: "#8b98a8", accent: "#4cc9f0" };
const DRAW_MS = 600;

function Curve({ points, color, reduced }: { points: EquityPoint[]; color: string; reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: COLORS.panel }, textColor: COLORS.muted, fontFamily: "JetBrains Mono", fontSize: 11, attributionLogo: false },
      grid: { vertLines: { color: COLORS.line }, horzLines: { color: COLORS.line } },
      rightPriceScale: { borderColor: COLORS.line },
      timeScale: { borderColor: COLORS.line, timeVisible: false },
      crosshair: { horzLine: { color: COLORS.muted }, vertLine: { color: COLORS.muted } },
      handleScroll: false,
      handleScale: false,
    });
    const series = chart.addSeries(LineSeries, {
      color, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
      priceFormat: { type: "custom", formatter: (v: number) => pct(v, 1), minMove: 0.001 },
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [color]);

  useEffect(() => {
    const series = seriesRef.current, chart = chartRef.current;
    if (!series || !chart) return;
    const data = toSeries(points);
    if (data.length === 0 || reduced) {
      series.setData(data);
      chart.timeScale().fitContent();
      return;
    }
    let raf = 0;
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / DRAW_MS);
      series.setData(data.slice(0, Math.max(1, Math.round(p * data.length))));
      chart.timeScale().fitContent();
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [points, reduced]);

  return <div ref={ref} className="h-full min-h-0 w-full" />;
}

function Legend({ label, stats, color }: { label: string; stats: Stats | null; color: string }) {
  return (
    <div className="flex items-baseline gap-3 font-mono text-[11px]">
      <span className="font-semibold tracking-[0.14em]" style={{ color }}>{label}</span>
      {stats ? (
        <>
          <span className="text-muted">n <span className="text-text">{int(stats.n)}</span></span>
          <span className="text-muted">mean <span className="text-text">{pct(stats.mean)}</span></span>
          <span className="text-muted">95% <span className="text-text">[{pct(stats.ci_low)}, {pct(stats.ci_high)}]</span></span>
          <span className="text-muted">win <span className="text-text">{(stats.win_rate * 100).toFixed(0)}%</span></span>
        </>
      ) : (
        <span className="text-muted">waiting for backtest</span>
      )}
    </div>
  );
}

function BaselineStrip({ stats }: { stats: NonNullable<UiState["stats"]> }) {
  const rows = [
    { label: "v0 validation mean", value: stats.validation.mean, color: COLORS.accent },
    { label: "no-condition baseline", value: stats.baseline.mean, color: COLORS.muted },
  ];
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
  const paired = stats.baseline.paired_ci_low;
  return (
    <div className="grid grid-cols-[auto_1fr_auto] items-center gap-x-4 gap-y-1 border-t border-line pt-3 font-mono text-[11px]">
      {rows.map((r) => (
        <div key={r.label} className="contents">
          <span className="text-muted">{r.label}</span>
          <svg viewBox="0 0 200 10" preserveAspectRatio="none" className="h-2.5 w-full" aria-hidden>
            <line x1={100} y1={0} x2={100} y2={10} stroke={COLORS.line} />
            <rect x={r.value < 0 ? 100 - (Math.abs(r.value) / max) * 98 : 100} y={2} width={(Math.abs(r.value) / max) * 98} height={6} fill={r.color} />
          </svg>
          <span className="text-right text-text">{pct(r.value)}</span>
        </div>
      ))}
      <span className="col-span-3 pt-1 text-muted">
        paired lower bound (v0 minus baseline, 2.5th pct) <span style={{ color: paired > 0 ? "var(--color-promising)" : "var(--color-inconclusive)" }}>{pct(paired)}</span>
      </span>
    </div>
  );
}

export function EquityCurves({ state, reduced }: { state: UiState; reduced: boolean }) {
  const { stats } = state;
  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)_auto] gap-3">
      <div className="grid grid-cols-2 gap-4">
        <Legend label="TRAIN" stats={stats?.train ?? null} color={COLORS.muted} />
        <Legend label="VALIDATION" stats={stats?.validation ?? null} color={COLORS.accent} />
      </div>
      <div className="grid min-h-0 grid-cols-2 gap-4">
        <Curve points={state.equityTrain} color={COLORS.muted} reduced={reduced} />
        <Curve points={state.equityValidation} color={COLORS.accent} reduced={reduced} />
      </div>
      {stats ? <BaselineStrip stats={stats} /> : <div className="border-t border-line pt-3 font-mono text-[11px] text-muted">cumulative return per trade, by entry date</div>}
    </div>
  );
}
