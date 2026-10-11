// Agent graph: the section 4 loop as a vertical list of five agents on a rail. HTML text, not a scaled SVG,
// so labels keep their real size (12-14 px) at 1280 and in a 1080p recording. Every animation marks an event:
// a row lights on agent_started and settles on agent_finished, a dot travels the rail when work moves
// (links.key changes), and the return arc lights once the Naysayer has requested follow-ups.
import { motion } from "framer-motion";
import type { Agent } from "../events";
import { AGENT_LABEL, agentOrder, type AgentStatus, type UiState } from "../state";

const STATUS_TEXT: Record<AgentStatus, string> = { idle: "standby", active: "active", done: "done", error: "error" };
const STATUS_COLOR: Record<AgentStatus, string> = { idle: "text-muted", active: "text-accent", done: "text-promising", error: "text-kill" };
const ROW_BORDER: Record<AgentStatus, string> = { idle: "border-line", active: "border-accent", done: "border-promising/50", error: "border-kill" };
const MARKER: Record<AgentStatus, string> = { idle: "border-line bg-bg", active: "border-accent bg-accent", done: "border-promising bg-promising", error: "border-kill bg-kill" };

const ROW = 44, GAP = 6, STEP = ROW + GAP, RAIL_X = 11;
const centre = (a: Agent) => agentOrder.indexOf(a) * STEP + ROW / 2;

export function AgentGraph({ state, reduced }: { state: UiState; reduced: boolean }) {
  const followups = state.followups.length;
  const height = agentOrder.length * STEP - GAP;
  const yM = centre("mathematician"), yN = centre("naysayer");
  return (
    <div className="relative shrink-0" style={{ height }}>
      {/* rail and one marker per agent */}
      <div aria-hidden className="absolute w-0.5 bg-line" style={{ left: RAIL_X - 1, top: ROW / 2, height: height - ROW }} />
      {agentOrder.map((a) => (
        <span key={a} aria-hidden className={`absolute size-3 rounded-full border-2 transition-colors duration-200 ${MARKER[state.agents[a]]}`} style={{ left: RAIL_X - 6, top: centre(a) - 6 }} />
      ))}

      {/* travelling dot, remounted on every handoff */}
      {!reduced && state.links && (
        <motion.span
          key={state.links.key}
          aria-hidden
          className="absolute size-3 rounded-full bg-accent shadow-[0_0_10px_var(--color-accent)]"
          style={{ left: RAIL_X - 6, top: 0 }}
          initial={{ y: centre(state.links.from) - 6, opacity: 1 }}
          animate={{ y: centre(state.links.to) - 6, opacity: [1, 1, 0] }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        />
      )}

      {/* return arc: the Naysayer sends follow-ups back to the Mathematician */}
      <svg aria-hidden className="absolute top-0 right-0 overflow-visible" width={40} height={height}>
        <path
          d={`M 0 ${yN} C 34 ${yN}, 34 ${yM}, 0 ${yM}`}
          fill="none"
          strokeWidth={2}
          strokeDasharray="5 5"
          style={{ stroke: followups ? "var(--color-accent)" : "var(--color-line)", transition: "stroke 200ms" }}
        />
        {followups > 0 && (
          <text x={30} y={(yM + yN) / 2 + 4} className="font-mono" fontSize={12} fill="var(--color-accent)">×{followups}</text>
        )}
      </svg>

      <ol aria-label="Agents" className="flex flex-col pr-11 pl-7" style={{ gap: GAP }}>
        {agentOrder.map((agent) => {
          const status = state.agents[agent];
          const glow = status === "active" && !reduced ? "shadow-[0_0_14px_-4px_var(--color-accent)]" : "";
          return (
            <li
              key={agent}
              className={`flex min-w-0 items-center justify-between gap-3 rounded-md border bg-bg px-3 transition-[border-color,box-shadow] duration-200 ${ROW_BORDER[status]} ${glow}`}
              style={{ height: ROW }}
            >
              <span className={`truncate text-sm font-semibold ${status === "idle" ? "text-muted" : "text-text"}`}>{AGENT_LABEL[agent]}</span>
              <span className="flex shrink-0 items-center gap-2">
                {agent === "researcher" && state.recoveries.map((r, i) => (
                  <span
                    key={i}
                    title={`Recovered: ${r.failed} → ${r.action}`}
                    className={`rounded-full border px-2 font-mono text-xs ${r.injected ? "border-inconclusive/60 text-inconclusive" : "border-kill/60 text-kill"}`}
                  >
                    {r.injected ? "↺ injected" : "↺ real"}
                  </span>
                ))}
                <span className={`font-mono text-xs uppercase tracking-[0.08em] ${STATUS_COLOR[status]}`}>
                  {agent === "naysayer" && followups > 0 && <span className="sr-only">{followups} follow-ups requested, </span>}
                  {STATUS_TEXT[status]}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
