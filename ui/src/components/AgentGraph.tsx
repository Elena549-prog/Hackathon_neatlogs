// Agent graph: the section 4 loop as five nodes. Every animation marks an event:
// a node lights on agent_started, settles on agent_finished, a dot travels a link when work moves
// (links.key changes), and the return arc animates on each followup_requested.
import { motion } from "framer-motion";
import type { Agent } from "../events";
import { agentOrder, type AgentStatus, type UiState } from "../state";

const W = 760, H = 420, NODE_W = 124, NODE_H = 64, Y = 190;
const X: Record<Agent, number> = { planner: 78, researcher: 229, mathematician: 380, naysayer: 531, reporter: 682, triage: 78 };
const LABEL: Record<Agent, string> = { planner: "Planner", researcher: "Researcher", mathematician: "Mathematician", naysayer: "Naysayer", reporter: "Reporter", triage: "Triage" };
const STROKE: Record<AgentStatus, string> = { idle: "var(--color-line)", active: "var(--color-accent)", done: "var(--color-promising)", error: "var(--color-kill)" };
const RETURN_ARC = `M ${X.naysayer} ${Y + NODE_H / 2} C ${X.naysayer} ${Y + 150}, ${X.mathematician} ${Y + 150}, ${X.mathematician} ${Y + NODE_H / 2}`;

function linkPath(from: Agent, to: Agent): string {
  if (from === "naysayer" && to === "mathematician") return RETURN_ARC;
  const [a, b] = X[from] < X[to] ? [X[from] + NODE_W / 2, X[to] - NODE_W / 2] : [X[from] - NODE_W / 2, X[to] + NODE_W / 2];
  return `M ${a} ${Y} L ${b} ${Y}`;
}

export function AgentGraph({ state, reduced }: { state: UiState; reduced: boolean }) {
  const followups = state.followups.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="Agent pipeline">
      {/* forward chain */}
      {agentOrder.slice(0, -1).map((from, i) => {
        const to = agentOrder[i + 1];
        return <path key={from} d={linkPath(from, to)} stroke="var(--color-line)" strokeWidth={2} fill="none" />;
      })}
      {/* return arc: naysayer asks the mathematician for follow-ups */}
      <path d={RETURN_ARC} stroke={followups ? "var(--color-accent)" : "var(--color-line)"} strokeWidth={2} fill="none" strokeDasharray="6 6" opacity={followups ? 0.9 : 0.5} />
      <text x={(X.naysayer + X.mathematician) / 2} y={Y + 128} textAnchor="middle" className="font-mono" fontSize={11} fill={followups ? "var(--color-accent)" : "var(--color-muted)"}>
        follow-ups ×{followups}
      </text>

      {/* travelling dot, remounted on every handoff */}
      {!reduced && state.links && (
        <circle key={state.links.key} r={5} fill="var(--color-accent)">
          <animateMotion dur="0.5s" path={linkPath(state.links.from, state.links.to)} fill="freeze" calcMode="spline" keySplines="0.16 1 0.3 1" keyTimes="0;1" />
        </circle>
      )}

      {agentOrder.map((agent) => {
        const status = state.agents[agent];
        const active = status === "active";
        const x = X[agent] - NODE_W / 2, y = Y - NODE_H / 2;
        return (
          <g key={agent}>
            <motion.rect
              x={x} y={y} width={NODE_W} height={NODE_H} rx={6}
              fill="var(--color-bg)"
              stroke={STROKE[status]}
              strokeWidth={active ? 2 : 1.5}
              style={{ transformBox: "fill-box", transformOrigin: "center", filter: active && !reduced ? "drop-shadow(0 0 10px var(--color-accent))" : "none" }}
              animate={{ scale: active && !reduced ? 1.05 : 1 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            />
            <text x={X[agent]} y={Y - 4} textAnchor="middle" fontSize={15} fontWeight={600} fill={status === "idle" ? "var(--color-muted)" : "var(--color-text)"}>
              {LABEL[agent]}
            </text>
            <text x={X[agent]} y={Y + 18} textAnchor="middle" className="font-mono" fontSize={10} letterSpacing={1.5} fill={STROKE[status === "idle" ? "idle" : status]} style={{ textTransform: "uppercase" }}>
              {status === "idle" ? "standby" : status}
            </text>
            {agent === "researcher" && state.recoveries.map((r, i) => (
              <g key={i}>
                <rect x={X.researcher - 66} y={y - 30 - i * 22} width={132} height={18} rx={9} fill="var(--color-panel)" stroke={r.injected ? "var(--color-inconclusive)" : "var(--color-kill)"} />
                <text x={X.researcher} y={y - 17 - i * 22} textAnchor="middle" className="font-mono" fontSize={10} letterSpacing={1} fill={r.injected ? "var(--color-inconclusive)" : "var(--color-kill)"}>
                  <title>{`${r.failed}: ${r.action}`}</title>
                  {r.injected ? "RECOVERED · INJECTED" : "RECOVERED · REAL"}
                </text>
              </g>
            ))}
          </g>
        );
      })}
    </svg>
  );
}
