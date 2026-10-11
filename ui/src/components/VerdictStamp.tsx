// Verdict stamp: lands on the verdict event (the one long animation, 900 ms), headline figures count
// up from zero. Copy for the subtitles is fixed by AUDITOR_SPEC.md sections 1 and 9.
import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import type { Verdict } from "../events";
import { int, pct } from "../fmt";
import type { UiState } from "../state";
import { countUp } from "./countUp";

const STAMP: Record<Verdict, { label: string; color: string }> = {
  kill: { label: "KILLED", color: "var(--color-kill)" },
  inconclusive: { label: "INCONCLUSIVE", color: "var(--color-inconclusive)" },
  promising: { label: "PROMISING", color: "var(--color-promising)" },
  cannot_audit: { label: "CANNOT AUDIT", color: "var(--color-cannot)" },
};
const SUBTITLE: Partial<Record<Verdict, string>> = {
  promising: "Passed a 6-month historical screen. Not a forecast. Not financial advice.",
  inconclusive: "inconclusive: a strategy with no real edge lands here about half the time",
};
const REVEAL_MS = 900;

function Figure({ label, value, format, reduced }: { label: string; value: number | undefined; format: (v: number) => string; reduced: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof value !== "number") return;
    return countUp(0, value, reduced ? 0 : REVEAL_MS, (v) => {
      el.textContent = format(v);
    });
  }, [value, format, reduced]);
  return (
    <div className="flex flex-col">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">{label}</span>
      <span ref={ref} className="font-mono text-2xl font-semibold tabular-nums text-text">{typeof value === "number" ? format(0) : "–"}</span>
    </div>
  );
}

export function VerdictStamp({ state, reduced, reportUrl, traceUrl }: { state: UiState; reduced: boolean; reportUrl: string | null; traceUrl: string | null }) {
  const v = state.verdict;
  if (!v) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-dashed border-line font-mono text-xs tracking-[0.2em] text-muted">
        {state.phase === "running" ? "VERDICT PENDING" : "NO AUDIT LOADED"}
      </div>
    );
  }
  const stamp = STAMP[v.verdict] ?? STAMP.cannot_audit;
  const showFigures = v.verdict !== "cannot_audit";
  return (
    <motion.div
      key={v.verdict}
      initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 1.15, rotate: -3 }}
      animate={{ opacity: 1, scale: 1, rotate: 0 }}
      transition={{ duration: REVEAL_MS / 1000, ease: [0.16, 1, 0.3, 1] }}
      className="grid h-full grid-cols-[auto_1fr_auto] items-center gap-8 rounded-md border-2 px-6 py-4"
      style={{ borderColor: stamp.color, background: `color-mix(in srgb, ${stamp.color} 8%, var(--color-panel))` }}
      role="status"
    >
      <div className="flex flex-col">
        <span className="font-sans text-5xl font-semibold tracking-[0.08em]" style={{ color: stamp.color }}>{stamp.label}</span>
        {SUBTITLE[v.verdict] && <span className="mt-1 max-w-md text-sm text-muted">{SUBTITLE[v.verdict]}</span>}
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <p className="text-sm text-text">{v.reason}</p>
        {showFigures && (
          <div className="grid grid-cols-4 gap-6">
            <Figure label="validation trades" value={v.headline.n} format={int} reduced={reduced} />
            <Figure label="mean per trade" value={v.headline.mean} format={pct} reduced={reduced} />
            <Figure label="lower bound" value={v.headline.ci_low} format={pct} reduced={reduced} />
            <Figure label="paired lower bound" value={v.headline.paired_ci_low} format={pct} reduced={reduced} />
          </div>
        )}
        {v.downgrades.length > 0 && (
          <ul className="flex flex-wrap gap-2 font-mono text-[11px]">
            {v.downgrades.map((d, i) => (
              <li key={i} className="rounded-full border border-inconclusive/60 px-2 py-0.5 text-inconclusive">
                downgrade: {typeof d.cause === "string" ? d.cause : JSON.stringify(d)}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-col gap-2 font-mono text-xs">
        <a
          href={reportUrl ?? "#"}
          target="_blank"
          rel="noreferrer"
          aria-disabled={!reportUrl}
          className={`rounded border border-line px-3 py-1.5 text-center transition-colors duration-150 ${reportUrl ? "text-text hover:border-accent" : "pointer-events-none text-muted opacity-50"}`}
        >
          Report
        </a>
        <a
          href={traceUrl ?? "#"}
          target="_blank"
          rel="noreferrer"
          aria-disabled={!traceUrl}
          title={traceUrl ? "Open the neatlogs trace" : "trace URL format to be verified"}
          className={`rounded border border-line px-3 py-1.5 text-center transition-colors duration-150 ${traceUrl ? "text-text hover:border-accent" : "pointer-events-none text-muted opacity-50"}`}
        >
          neatlogs trace
        </a>
      </div>
    </motion.div>
  );
}
