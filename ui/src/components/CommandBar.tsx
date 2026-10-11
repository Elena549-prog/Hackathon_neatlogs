import { useState, type FormEvent, type ReactNode } from "react";
import type { UiState } from "../state";
import { displayIdea, runLabel } from "../useAudit";

export interface Chip {
  label: string;
  available: boolean;
}

function runDate(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export function CommandBar({ state, mode, chips, onSubmit, controls, error, onDismissError }: {
  state: UiState; mode: "replay" | "live"; chips: Chip[]; onSubmit: (text: string) => void; controls: ReactNode;
  error: string | null; onDismissError: () => void;
}) {
  const [text, setText] = useState("");
  // The input always names the recording on screen, whether it was typed or picked from a chip
  // (adjusting state while rendering, React's pattern for "reset when a prop changes").
  const [shownIdea, setShownIdea] = useState(state.idea);
  if (state.idea !== shownIdea) {
    setShownIdea(state.idea);
    if (state.idea) setText(displayIdea(state.idea));
  }
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(text);
  };
  const isReplay = mode === "replay";
  const label = runLabel(state.idea, state.provider);
  return (
    <section className="rounded-md border border-line bg-panel px-4 py-3">
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 items-baseline gap-3">
          <h1 className="text-base font-semibold tracking-tight">Strategy Auditor</h1>
          <span className="hidden font-mono text-xs uppercase tracking-[0.08em] text-muted 2xl:inline">mission control</span>
        </div>
        <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type a recorded trading idea, or pick one below…"
            aria-label="Trading idea"
            required
            minLength={3}
            className="h-9 min-w-0 flex-1 rounded border border-muted/60 bg-bg px-3 text-sm text-text placeholder:text-muted focus:border-accent"
          />
          <button type="submit" className="h-9 shrink-0 rounded bg-accent px-4 text-sm font-semibold text-bg transition-[filter] duration-150 hover:brightness-110">
            Audit
          </button>
        </form>
        <span
          className={`flex h-7 shrink-0 items-center gap-2 rounded-full border px-3 font-mono text-xs font-semibold tracking-[0.08em] ${isReplay ? "border-inconclusive/60 text-inconclusive" : "border-promising/60 text-promising"}`}
          title={isReplay ? "Replaying a recorded events.jsonl" : "Live audit"}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${isReplay ? "bg-inconclusive" : "bg-promising"}`} />
          {isReplay ? "REPLAY" : "LIVE"}
          {isReplay && state.startedAt && <span className="font-normal text-muted">· {runDate(state.startedAt)}</span>}
        </span>
        {controls}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {chips.map((c) => (
          <button
            key={c.label}
            type="button"
            onClick={() => onSubmit(c.label)}
            disabled={!c.available}
            title={c.available ? `Replay the recorded audit of "${c.label}"` : "Not recorded yet: run scripts/demo_audits.py to record it"}
            className="rounded-full border border-line bg-bg px-3 py-1 text-xs text-muted transition-colors duration-150 enabled:hover:border-accent enabled:hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
          >
            {c.label}
            {!c.available && <span className="ml-1">· not recorded</span>}
          </button>
        ))}
        {error ? (
          <div role="alert" className="flex min-w-0 flex-1 items-center gap-3 pl-2 text-sm text-kill">
            <span className="min-w-0">{error}</span>
            <button type="button" onClick={onDismissError} className="shrink-0 rounded border border-line px-2 py-0.5 text-xs text-text transition-colors duration-150 hover:border-accent">
              Dismiss
            </button>
          </div>
        ) : (
          <div className="min-w-0 flex-1 truncate pl-2 text-sm" aria-live="polite">
            {state.whatTested ? (
              <>
                <span className="font-mono text-xs uppercase tracking-[0.08em] text-muted">tested </span>
                <span className="text-text">{state.whatTested}</span>
                {state.planHash && <span className="ml-2 font-mono text-xs text-muted">v0 {state.planHash.slice(0, 12)}</span>}
              </>
            ) : null}
          </div>
        )}
        {label && (
          <span className="flex h-7 shrink-0 items-center rounded-full border border-kill/70 px-3 font-mono text-xs font-semibold tracking-[0.08em] text-kill" title={state.idea}>
            {label}
          </span>
        )}
      </div>
    </section>
  );
}
