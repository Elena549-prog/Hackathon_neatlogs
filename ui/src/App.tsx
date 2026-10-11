import { useReducedMotion } from "framer-motion";
import { AgentGraph } from "./components/AgentGraph";
import { CommandBar } from "./components/CommandBar";
import { EquityCurves } from "./components/EquityCurves";
import { FooterMeters } from "./components/FooterMeters";
import { Panel } from "./components/Panel";
import { ReplayControls } from "./components/ReplayControls";
import { VerdictStamp } from "./components/VerdictStamp";
import { useAudit } from "./useAudit";

// Demo ideas, exact text from AUDITOR_SPEC.md section 13.
export const DEMO_IDEAS = ["buy dips in an uptrend", "buy straddles on tech before earnings", "sell straddles on low-volatility mega-caps"];

export default function App() {
  const a = useAudit();
  const reduced = useReducedMotion() ?? false;
  const state = a.state;
  const canResume = !!a.currentAuditId && state.phase !== "done";
  const elapsedMs = state.startedAt && state.lastTs ? Date.parse(state.lastTs) - Date.parse(state.startedAt) : 0;
  const reportUrl = a.currentAuditId && state.report ? `/api/audits/${encodeURIComponent(a.currentAuditId)}/report` : null;

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)_auto_auto] gap-3 p-4">
      <CommandBar
        state={a.state}
        mode={a.mode}
        chips={DEMO_IDEAS}
        onSubmit={a.submitIdea}
        controls={
          <ReplayControls
            playing={a.playing}
            speed={a.speed}
            onPlay={a.resume}
            onPause={a.pause}
            onSpeed={a.setSpeed}
            disabled={!a.playing && !canResume}
          />
        }
      />
      <div className="grid min-h-0 grid-cols-[5fr_7fr] gap-3">
        <Panel title="Agents" right={state.lastAgent && <span className="font-mono text-[11px] text-muted">{state.lastAgent}</span>}>
          <AgentGraph state={state} reduced={reduced} />
        </Panel>
        <Panel title="Evidence" right={state.equityRun && <span className="font-mono text-[11px] text-muted">run: {state.equityRun}</span>}>
          <EquityCurves state={state} reduced={reduced} />
        </Panel>
      </div>
      <div className="h-40">
        <VerdictStamp state={state} reduced={reduced} reportUrl={reportUrl} traceUrl={null} />
      </div>
      <FooterMeters state={state} elapsedMs={Number.isFinite(elapsedMs) ? elapsedMs : 0} followupsRun={state.followupsRun} />
      {a.state.errors.length > 0 && (
        <div role="alert" className="fixed right-4 bottom-16 max-w-md rounded border border-kill/60 bg-panel px-4 py-3 text-sm text-text shadow-lg">
          {a.state.errors[a.state.errors.length - 1]}
        </div>
      )}
    </div>
  );
}
