import { useReducedMotion } from "framer-motion";
import { AgentGraph } from "./components/AgentGraph";
import { CommandBar } from "./components/CommandBar";
import { EquityCurves } from "./components/EquityCurves";
import { Panel } from "./components/Panel";
import { ReplayControls } from "./components/ReplayControls";
import { useAudit } from "./useAudit";

// Demo ideas, exact text from AUDITOR_SPEC.md section 13.
export const DEMO_IDEAS = ["buy dips in an uptrend", "buy straddles on tech before earnings", "sell straddles on low-volatility mega-caps"];

export default function App() {
  const a = useAudit();
  const reduced = useReducedMotion() ?? false;
  const state = a.state;
  const canResume = !!a.currentAuditId && state.phase !== "done";

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
      <Panel title="Verdict">
        <p className="text-sm text-muted">verdict stamp (Task 9)</p>
      </Panel>
      <footer className="flex items-center justify-between rounded-md border border-line bg-panel px-4 py-2 font-mono text-xs text-muted">
        <span>footer meters (Task 9)</span>
        <span>seq {a.state.lastSeq}</span>
      </footer>
      {a.state.errors.length > 0 && (
        <div role="alert" className="fixed right-4 bottom-16 max-w-md rounded border border-kill/60 bg-panel px-4 py-3 text-sm text-text shadow-lg">
          {a.state.errors[a.state.errors.length - 1]}
        </div>
      )}
    </div>
  );
}
