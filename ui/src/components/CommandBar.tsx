import { useState, type FormEvent, type ReactNode } from "react";
import type { UiState } from "../state";

function runDate(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export function CommandBar({ state, mode, chips, onSubmit, controls }: {
  state: UiState; mode: "replay" | "live"; chips: string[]; onSubmit: (text: string) => void; controls: ReactNode;
}) {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(text);
  };
  const isReplay = mode === "replay";
  return (
    <section className="rounded-md border border-line bg-panel px-4 py-3">
      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-3">
          <h1 className="text-base font-semibold tracking-tight">Strategy Auditor</h1>
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">mission control</span>
        </div>
        <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type a trading idea…"
            aria-label="Trading idea"
            className="h-9 min-w-0 flex-1 rounded border border-line bg-bg px-3 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none"
          />
          <button type="submit" className="h-9 rounded bg-accent px-4 text-sm font-semibold text-bg transition-colors duration-150 hover:brightness-110">
            Audit
          </button>
        </form>
        <span
          className={`flex h-7 items-center gap-2 rounded-full border px-3 font-mono text-[11px] font-semibold tracking-[0.14em] ${isReplay ? "border-inconclusive/60 text-inconclusive" : "border-promising/60 text-promising"}`}
          title={isReplay ? "Replaying a recorded events.jsonl" : "Live audit"}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${isReplay ? "bg-inconclusive" : "bg-promising"}`} />
          {isReplay ? "REPLAY" : "LIVE"}
          {isReplay && state.startedAt && <span className="font-normal text-muted">· {runDate(state.startedAt)}</span>}
        </span>
        {controls}
      </div>
      <div className="mt-2 flex items-center gap-2">
        {chips.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onSubmit(c)}
            className="rounded-full border border-line bg-bg px-3 py-1 text-xs text-muted transition-colors duration-150 hover:border-accent hover:text-text"
          >
            {c}
          </button>
        ))}
        <div className="min-w-0 flex-1 truncate pl-2 text-xs" aria-live="polite">
          {state.whatTested ? (
            <>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">tested </span>
              <span className="text-text">{state.whatTested}</span>
              {state.planHash && <span className="ml-2 font-mono text-[11px] text-muted">v0 {state.planHash.slice(0, 12)}</span>}
            </>
          ) : state.idea ? (
            <span className="text-muted">idea: {state.idea}</span>
          ) : null}
        </div>
      </div>
    </section>
  );
}
