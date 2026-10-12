// Verdict stamp: lands on the verdict event (the one long animation, 900 ms), headline figures count
// up from zero. Copy for the subtitles is fixed by AUDITOR_SPEC.md sections 1 and 9.
import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import type { Verdict } from "../events";
import { int, pct } from "../fmt";
import type { UiState } from "../state";
import { runLabel } from "../useAudit";
import { countUp } from "./countUp";

const STAMP: Record<Verdict, { label: string; color: string }> = {
  kill: { label: "KILLED", color: "var(--color-kill)" },
  inconclusive: { label: "INCONCLUSIVE", color: "var(--color-inconclusive)" },
  promising: { label: "PROMISING", color: "var(--color-promising)" },
  cannot_audit: { label: "CANNOT AUDIT", color: "var(--color-cannot)" },
  trade: { label: "APPROVED · PAPER TRADE", color: "var(--color-promising)" },
  no_trade: { label: "NO TRADE", color: "var(--color-cannot)" },
};
const SUBTITLE: Record<Verdict, string> = {
  kill: "Enough evidence, and the validation mean return per trade is 0 or below.",
  promising: "Passed a 6-month historical screen. Not a forecast. Not financial advice.",
  inconclusive: "inconclusive: a strategy with no real edge lands here about half the time",
  cannot_audit: "Refused, outside the supported families, core of the idea not testable, or no valid plan.",
  trade: "The gate passed and the Naysayer approved. The simulator closed the position on real prices.",
  no_trade: "The Naysayer blocked the plan, so no position was opened.",
};
const price = (v: number) => `$${v.toFixed(2)}`;
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
      <span className="font-mono text-xs uppercase tracking-[0.08em] text-muted">{label}</span>
      <span ref={ref} className="font-mono text-2xl font-semibold tabular-nums text-text">{typeof value === "number" ? format(0) : "–"}</span>
    </div>
  );
}

export function VerdictStamp({ state, reduced, reportUrl, traceUrl }: { state: UiState; reduced: boolean; reportUrl: string | null; traceUrl: string | null }) {
  const v = state.verdict;
  if (!v) {
    // A thin bar until the verdict lands, so the panels above get the room while the agents work.
    return (
      <div className="flex h-10 items-center justify-center rounded-md border border-dashed border-line px-4 text-sm text-muted">
        {state.phase === "running" ? (
          <span className="font-mono text-xs uppercase tracking-[0.08em]">Verdict pending</span>
        ) : state.phase === "done" ? (
          "The audit stopped before a verdict. The error is shown above."
        ) : (
          "Pick a recorded idea above to replay its audit, from the plan to the verdict."
        )}
      </div>
    );
  }
  const stamp = STAMP[v.verdict] ?? STAMP.cannot_audit;
  const showFigures = v.verdict !== "cannot_audit" && v.verdict !== "no_trade";
  return (
    <motion.div
      key={v.verdict}
      initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 1.15, rotate: -3 }}
      animate={{ opacity: 1, scale: 1, rotate: 0 }}
      transition={{ duration: REVEAL_MS / 1000, ease: [0.16, 1, 0.3, 1] }}
      className="grid min-h-40 grid-cols-[auto_1fr_auto] items-center gap-8 rounded-md border-2 px-6 py-4"
      style={{ borderColor: stamp.color, background: `color-mix(in srgb, ${stamp.color} 8%, var(--color-panel))` }}
      role="status"
    >
      <div className="flex flex-col">
        <span className="font-sans text-5xl font-semibold tracking-[0.08em]" style={{ color: stamp.color }}>{stamp.label}</span>
        {SUBTITLE[v.verdict] && <span className="mt-1 max-w-md text-sm text-muted">{SUBTITLE[v.verdict]}</span>}
        {runLabel(state.idea, state.provider) && <span className="mt-1 font-mono text-xs font-semibold tracking-[0.08em] text-kill">{runLabel(state.idea, state.provider)}</span>}
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <p className="max-w-[65ch] text-sm text-text">{v.reason}</p>
        {showFigures && v.verdict === "trade" && (
          <div className="grid grid-cols-4 gap-6">
            <Figure label="entry" value={v.headline.entry} format={price} reduced={reduced} />
            <Figure label="exit" value={v.headline.exit} format={price} reduced={reduced} />
            <Figure label="days held" value={v.headline.days} format={int} reduced={reduced} />
            <Figure label="p&l" value={v.headline.pnl} format={pct} reduced={reduced} />
          </div>
        )}
        {showFigures && v.verdict !== "trade" && (
          <div className="grid grid-cols-4 gap-6">
            <Figure label="validation trades" value={v.headline.n} format={int} reduced={reduced} />
            <Figure label="mean per trade" value={v.headline.mean} format={pct} reduced={reduced} />
            <Figure label="lower bound" value={v.headline.ci_low} format={pct} reduced={reduced} />
            <Figure label="paired lower bound" value={v.headline.paired_ci_low} format={pct} reduced={reduced} />
          </div>
        )}
        {v.downgrades.length > 0 && (
          <ul className="flex flex-wrap gap-2 font-mono text-xs">
            {v.downgrades.map((d, i) => (
              <li key={i} title={typeof d.cause === "string" ? d.cause : undefined} className="max-w-[65ch] rounded border border-inconclusive/60 px-3 py-1 text-inconclusive">
                downgrade: {typeof d.cause === "string" ? d.cause : JSON.stringify(d)}
              </li>
            ))}
          </ul>
        )}
      </div>
      {/* Links render only once they lead somewhere: a disabled link is still reachable with Tab. */}
      <div className="flex flex-col gap-2 font-mono text-xs">
        {reportUrl && (
          <a href={reportUrl} target="_blank" rel="noreferrer" className="rounded border border-line px-3 py-1.5 text-center text-text transition-colors duration-150 hover:border-accent">
            Report
          </a>
        )}
        {traceUrl && (
          <a href={traceUrl} target="_blank" rel="noreferrer" title="Open the neatlogs trace" className="rounded border border-line px-3 py-1.5 text-center text-text transition-colors duration-150 hover:border-accent">
            neatlogs trace
          </a>
        )}
      </div>
    </motion.div>
  );
}
