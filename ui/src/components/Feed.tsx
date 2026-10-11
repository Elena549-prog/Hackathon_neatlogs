// Activity feed (spec 16, item 3): terse lines for agent starts and finishes, LLM calls, tool calls, data
// progress, follow-up requests and recoveries (REAL or INJECTED). Fills the stretch where the panels are
// still waiting. Each line fades in once (180 ms); the list keeps the newest line in view.
import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import { AGENT_LABEL, type FeedLine, type UiState } from "../state";

const TONE: Record<FeedLine["tone"], string> = { info: "text-text/80", ok: "text-text", bad: "text-kill", injected: "text-inconclusive" };

function offset(ts: string, start: string | null): string {
  const ms = start ? Date.parse(ts) - Date.parse(start) : NaN;
  if (!Number.isFinite(ms)) return "--:--";
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function Feed({ state, reduced }: { state: UiState; reduced: boolean }) {
  const ref = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [state.feed.length]);

  if (state.feed.length === 0) {
    return (
      <p className="text-sm text-muted">
        {state.phase === "idle" ? "Each agent step, tool call and LLM call is listed here as the audit replays." : "Waiting for the first agent step…"}
      </p>
    );
  }
  return (
    <ol ref={ref} role="log" aria-label="Agent activity" className="-mr-2 h-full overflow-y-auto pr-2 font-mono text-xs leading-relaxed">
      {state.feed.map((l) => (
        <motion.li
          key={l.seq}
          initial={reduced ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
          className="grid grid-cols-[3rem_minmax(0,1fr)] gap-2 py-0.5"
        >
          <span className="tabular-nums text-muted">{offset(l.ts, state.startedAt)}</span>
          <span className={`break-words ${TONE[l.tone]}`}>
            {l.agent && <span className="mr-2 font-semibold text-text">{AGENT_LABEL[l.agent]}</span>}
            {l.text}
          </span>
        </motion.li>
      ))}
    </ol>
  );
}
