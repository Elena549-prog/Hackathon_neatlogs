import { useReducedMotion } from "framer-motion";
import { AgentGraph } from "./components/AgentGraph";
import { CommandBar } from "./components/CommandBar";
import { EquityCurves } from "./components/EquityCurves";
import { Feed } from "./components/Feed";
import { FooterMeters } from "./components/FooterMeters";
import { Objections } from "./components/Objections";
import { Panel } from "./components/Panel";
import { ReplayControls } from "./components/ReplayControls";
import { VerdictStamp } from "./components/VerdictStamp";
import { AGENT_LABEL } from "./state";
import { pickAudit, useAudit } from "./useAudit";

// Demo ideas, exact text from AUDITOR_SPEC.md section 13.
export const DEMO_IDEAS = ["buy dips in an uptrend", "buy straddles on tech before earnings", "sell straddles on low-volatility mega-caps"];

export default function App() {
  const a = useAudit();
  const reduced = useReducedMotion() ?? false;
  const state = a.state;
  const done = state.phase === "done" && !a.playing;
  const canResume = !!a.currentAuditId && state.phase !== "done";
  const elapsedMs = state.startedAt && state.lastTs ? Date.parse(state.lastTs) - Date.parse(state.startedAt) : 0;
  const reportUrl = a.currentAuditId && state.report ? `/api/audits/${encodeURIComponent(a.currentAuditId)}/report` : null;
  // A chip is offered only when a recording of exactly that idea exists, so no chip leads to an error.
  const chips = DEMO_IDEAS.map((label) => ({ label, available: pickAudit(a.audits, label) !== null }));

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)_auto_auto] gap-3 p-4">
      <CommandBar
        state={a.state}
        mode={a.mode}
        chips={chips}
        onSubmit={a.submitIdea}
        error={state.errors.length > 0 ? state.errors[state.errors.length - 1] : null}
        onDismissError={a.dismissError}
        controls={
          <ReplayControls
            playing={a.playing}
            done={done && !!a.currentAuditId}
            speed={a.speed}
            onPlay={done && a.currentAuditId ? () => a.play(a.currentAuditId!) : a.resume}
            onPause={a.pause}
            onSpeed={a.setSpeed}
            disabled={!a.playing && !canResume && !(done && a.currentAuditId)}
          />
        }
      />
      <main className="grid min-h-0 grid-cols-[minmax(0,7fr)_minmax(0,9fr)_minmax(0,6fr)] gap-3">
        <Panel title="Agents" right={state.lastAgent && <span className="font-mono text-xs text-muted">{AGENT_LABEL[state.lastAgent]}</span>}>
          <div className="flex h-full min-h-0 flex-col gap-3">
            <AgentGraph state={state} reduced={reduced} />
            <div className="min-h-0 flex-1 border-t border-line pt-3">
              <Feed state={state} reduced={reduced} />
            </div>
          </div>
        </Panel>
        <Panel title="Evidence" right={state.equityRun && <span className="font-mono text-xs text-muted">run: {state.equityRun}</span>}>
          <EquityCurves state={state} reduced={reduced} />
        </Panel>
        <Panel title="Objections" right={state.followups.length > 0 && <span className="font-mono text-xs text-muted">follow-ups {state.followups.length}</span>}>
          <Objections state={state} reduced={reduced} />
        </Panel>
      </main>
      <VerdictStamp state={state} reduced={reduced} reportUrl={reportUrl} traceUrl={null} />
      <FooterMeters state={state} elapsedMs={Number.isFinite(elapsedMs) ? elapsedMs : 0} followupsRun={state.followupsRun} />
    </div>
  );
}
