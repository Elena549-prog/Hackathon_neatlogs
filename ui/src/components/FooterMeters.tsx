import { int, usd } from "../fmt";
import type { UiState } from "../state";

const mmss = (ms: number) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

function Meter({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-xs uppercase tracking-[0.08em] text-muted">{label}</span>
      <span className="tabular-nums text-text">{value}</span>
    </div>
  );
}

/** Running totals from the events: elapsed is event time (first to latest ts), so replay speed does not distort it. */
export function FooterMeters({ state, elapsedMs, followupsRun }: { state: UiState; elapsedMs: number; followupsRun: number }) {
  const m = state.meters;
  return (
    <footer className="flex items-center justify-between rounded-md border border-line bg-panel px-4 py-2 font-mono text-xs">
      <div className="flex items-center gap-8">
        <Meter label="elapsed" value={mmss(elapsedMs)} />
        <Meter label="llm calls" value={`${m.llmCalls} / ${m.budget}`} />
        <Meter label="tokens" value={int(m.promptTokens + m.completionTokens)} />
        <Meter label="cost" value={usd(m.costUsd)} />
        <Meter label="follow-ups run" value={String(followupsRun)} />
      </div>
      <Meter label="seq" value={String(state.lastSeq)} />
    </footer>
  );
}
