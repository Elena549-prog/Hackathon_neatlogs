// Objections panel (spec 16, item 5): the Naysayer's coded checks and its follow-ups, one card per event.
// Motion, all one-shot and tied to an event: a card lands (drops 10 px, settles from 102%, 320 ms, no bounce) and its
// border settles from the accent to its resting colour (600 ms) when its check_result or followup_requested arrives;
// a follow-up's result line and status badge appear when its backtest_result lands, and the badge changes once more
// when the verdict says whether the downgrade was applied. Reduced motion: opacity only, 150 ms.
import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import { appliedDowngrade, type Followup, type UiState } from "../state";

const EASE = [0.16, 1, 0.3, 1] as const;
// Hex copies of the index.css tokens: Framer can interpolate hex colours, not var() strings.
const HEX = { line: "#46352a", accent: "#efe0b9", amber: "#e2a548" };

const CHECK_LABEL: Record<string, string> = {
  evidence: "Evidence", leakage: "Leakage", decay: "Out-of-sample decay", shared_window: "Shared window",
  cost_realism: "Cost realism", tail_risk: "Tail risk", data_drops: "Data drops",
  // Swarm trade decision: the hard gate, then each Naysayer's verdict.
  gate_evidence: "Evidence", gate_breadth: "Breadth", gate_edge: "Edge vs break-even",
  naysayer_v1: "Naysayer v1", naysayer_v2: "Naysayer v2",
};
// The follow-up menu names from spec section 4, shown until the result's own title arrives.
const FOLLOWUP_TITLE: Record<string, string> = { F1: "Earnings excluded", F2: "Per-year stability", F3: "Horizon sensitivity", F4: "Concentration" };

function landing(reduced: boolean, rest: string) {
  return reduced
    ? { initial: { opacity: 0, borderColor: rest }, animate: { opacity: 1, borderColor: rest }, transition: { duration: 0.15 } }
    : {
        initial: { opacity: 0, y: -10, scale: 1.02, borderColor: HEX.accent },
        animate: { opacity: 1, y: 0, scale: 1, borderColor: rest },
        transition: { duration: 0.32, ease: EASE, borderColor: { duration: 0.6, ease: EASE } },
      };
}

/** Keeps a card that just landed or changed visible when the panel scrolls (1280×800). Instant on purpose: the
 *  card's own landing is the motion, and smooth scrolls cancel each other when events arrive close together. */
function useInView<T extends HTMLElement>(dep: unknown) {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.scrollIntoView?.({ block: "nearest" });
  }, [dep]);
  return ref;
}

function Heading({ children }: { children: string }) {
  return <h3 className="mb-2 font-mono text-xs uppercase tracking-[0.08em] text-muted">{children}</h3>;
}

function CheckCard({ c, reduced }: { c: UiState["checks"][number]; reduced: boolean }) {
  const ref = useInView<HTMLLIElement>(null);
  const label = CHECK_LABEL[c.check] ?? c.check.replace(/_/g, " ");
  return (
    <motion.li ref={ref} {...landing(reduced, c.passed ? HEX.line : HEX.amber)} className="rounded border bg-bg px-3 py-1" title={c.note}>
      <div className="flex min-w-0 items-baseline gap-2">
        <span className={`w-10 shrink-0 font-mono text-xs font-semibold tracking-[0.08em] ${c.passed ? "text-promising" : "text-inconclusive"}`}>
          {c.passed ? "PASS" : "FAIL"}
        </span>
        <span className="shrink-0 text-sm font-medium text-text">{label}</span>
        {/* Passed checks stay one quiet line; a failed check is an objection, so its note shows in full. */}
        {c.passed && <span className="min-w-0 truncate text-xs text-muted">{c.note}</span>}
      </div>
      {!c.passed && <p className="mt-0.5 pl-10 text-xs text-text/80">{c.note}</p>}
    </motion.li>
  );
}

function badge(f: Followup, verdict: UiState["verdict"]): { text: string; tone: "muted" | "amber" | "applied"; title?: string } {
  if (f.result === undefined && f.downgrade === undefined) return { text: "REQUESTED", tone: "muted" };
  if (f.skipped) return { text: "SKIPPED", tone: "muted" };
  if (!f.downgrade) return { text: "NO DOWNGRADE", tone: "muted" };
  // The rule text (cause) goes in the tooltip: the verdict stamp already lists every applied downgrade's cause.
  const rule = f.cause ? `rule: ${f.cause}` : "rule met";
  if (!verdict) return { text: "RULE MET", tone: "amber", title: rule };
  const applied = appliedDowngrade(f, verdict);
  if (applied) return { text: "RULE MET · APPLIED", tone: "applied", title: `${rule}\n${applied.from ?? "?"} → ${applied.to ?? "?"}` };
  return { text: "RULE MET · NOT APPLIED", tone: "muted", title: `${rule}\nfollow-ups only downgrade a promising verdict (verdict: ${verdict.verdict})` };
}

const TONE = {
  muted: "border-line text-muted",
  amber: "border-inconclusive/60 text-inconclusive",
  applied: "border-inconclusive bg-inconclusive text-bg",
};

function FollowupCard({ f, verdict, reduced }: { f: Followup; verdict: UiState["verdict"]; reduced: boolean }) {
  const b = badge(f, verdict);
  const ref = useInView<HTMLLIElement>(b.text);
  const enter = reduced ? { opacity: 0 } : { opacity: 0, y: 4 };
  return (
    <motion.li ref={ref} {...landing(reduced, f.downgrade ? HEX.amber : HEX.line)} className="rounded border bg-bg px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="font-mono text-xs font-semibold text-accent">{f.id}</span>
          <span className="truncate text-sm font-medium text-text">{f.title ?? FOLLOWUP_TITLE[f.id] ?? "follow-up"}</span>
        </div>
        <motion.span
          key={b.text}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduced ? 0.15 : 0.2, ease: EASE }}
          title={b.title}
          className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-xs font-semibold tracking-[0.08em] ${TONE[b.tone]}`}
        >
          {b.text}
        </motion.span>
      </div>
      {f.reason && (
        <p className="mt-1 text-xs text-muted">
          <span className="font-mono text-xs uppercase tracking-[0.08em]">why </span>
          {f.reason}
        </p>
      )}
      {f.result !== undefined && (
        <motion.p initial={enter} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0.15 : 0.24, ease: EASE }} className="mt-1 font-mono text-xs leading-snug text-text">
          {f.result}
        </motion.p>
      )}
    </motion.li>
  );
}

export function Objections({ state, reduced }: { state: UiState; reduced: boolean }) {
  const { checks, followups, verdict } = state;
  if (checks.length === 0 && followups.length === 0) {
    return <p className="text-sm text-muted">{state.phase === "idle" ? "The Naysayer's coded checks and the follow-ups it orders land here." : "Waiting for the Naysayer…"}</p>;
  }
  return (
    <div className="-mr-2 h-full overflow-y-auto pr-2">
      {checks.length > 0 && (
        <section>
          <Heading>Coded checks</Heading>
          <ul className="flex flex-col gap-1">
            {checks.map((c, i) => <CheckCard key={i} c={c} reduced={reduced} />)}
          </ul>
        </section>
      )}
      {followups.length > 0 && (
        <section className="mt-3">
          <Heading>Follow-ups</Heading>
          <ul className="flex flex-col gap-2">
            {followups.map((f) => <FollowupCard key={f.id} f={f} verdict={verdict} reduced={reduced} />)}
          </ul>
        </section>
      )}
    </div>
  );
}
