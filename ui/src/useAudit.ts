// Replay session: which audit plays, at what speed, paused or not. Live mode is stretch (spec 17).
import { useCallback, useEffect, useRef, useState } from "react";
import type { AuditSummary } from "./events";
import { initialState, reduce, type UiState } from "./state";
import { listAudits, openEvents } from "./stream";

const SYNTHETIC_PREFIX = "SYNTHETIC FIXTURE";
const SYNTHETIC_WRAP = /^SYNTHETIC FIXTURE:\s*|\s*\(not a real audit\)$/gi;
const MIN_QUERY = 3;

/** The development fixture labels itself through its idea text (scripts/synthetic_audit.py). */
export const isSynthetic = (idea: string): boolean => idea.startsWith(SYNTHETIC_PREFIX);

/** The idea as a person typed it: the fixture's label wrapper removed (the SYNTHETIC pill says that instead). */
export const displayIdea = (idea: string): string => idea.replace(SYNTHETIC_WRAP, "").trim();

/** Comparison key: case and spacing do not matter, nothing else is fuzzy. */
export const ideaKey = (idea: string): string => displayIdea(idea).toLowerCase().replace(/\s+/g, " ");

/** Actionable message for an idea with no recording: names what can be replayed. */
export function noRecording(text: string, audits: AuditSummary[]): string {
  const ideas = [...new Set(audits.map((a) => displayIdea(a.idea)))];
  return ideas.length
    ? `No recording of "${text.trim()}". Recorded ideas: ${ideas.join("; ")}.`
    : "No recordings yet. Record the demo ideas with scripts/demo_audits.py, then reload this page.";
}

/** Honesty label for the command bar and the stamp: synthetic fixture, fake-LLM run, or none for a real run. */
export function runLabel(idea: string, provider: string | null): string | null {
  if (isSynthetic(idea)) return "SYNTHETIC · NOT A REAL AUDIT";
  if (provider === "fake") return "FAKE LLM · KEYWORD PLANNER, REAL DATA";
  return null;
}

/** The recording to play for a typed idea or chip: same idea only (no partial matches, so "buy" never plays
 *  the dips audit); a real recording wins over the synthetic fixture; the server lists newest first. */
export function pickAudit(audits: AuditSummary[], text: string): AuditSummary | null {
  const k = ideaKey(text);
  if (k.length < MIN_QUERY) return null;
  const matches = audits.filter((a) => ideaKey(a.idea) === k);
  return matches.find((a) => !isSynthetic(a.idea)) ?? matches[0] ?? null;
}

export interface AuditSession {
  state: UiState;
  audits: AuditSummary[];
  mode: "replay" | "live";
  speed: number;
  setSpeed: (n: number) => void;
  playing: boolean;
  play: (auditId: string) => void;
  pause: () => void;
  resume: () => void;
  reset: () => void;
  currentAuditId: string | null;
  submitIdea: (text: string) => void;
  dismissError: () => void;
}

export function useAudit(): AuditSession {
  const [state, setState] = useState<UiState>(initialState);
  const [audits, setAudits] = useState<AuditSummary[]>([]);
  const [speed, setSpeedState] = useState(2);
  const [playing, setPlaying] = useState(false);
  const [currentAuditId, setCurrent] = useState<string | null>(null);
  const closeRef = useRef<(() => void) | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    listAudits()
      .then(setAudits)
      .catch((err: Error) => {
        setAudits([]);
        setState((s) => ({ ...s, errors: [...s.errors, `Could not load the recordings (${err.message}). Is the server running?`] }));
      });
    return () => closeRef.current?.();
  }, []);

  const open = useCallback((auditId: string, from: number, spd: number) => {
    closeRef.current?.();
    closeRef.current = openEvents(auditId, {
      replay: true,
      speed: spd,
      from,
      onEvent: (e) => setState((s) => reduce(s, e)),
      onEnd: () => {
        closeRef.current = null;
        setPlaying(false);
      },
      onError: (msg) => {
        closeRef.current = null;
        setPlaying(false);
        setState((s) => ({ ...s, errors: [...s.errors, msg] }));
      },
    });
    setPlaying(true);
  }, []);

  const play = useCallback(
    (auditId: string) => {
      setState(initialState);
      setCurrent(auditId);
      open(auditId, 0, speed);
    },
    [open, speed],
  );

  const pause = useCallback(() => {
    closeRef.current?.();
    closeRef.current = null;
    setPlaying(false);
  }, []);

  const resume = useCallback(() => {
    if (currentAuditId && stateRef.current.phase !== "done") open(currentAuditId, stateRef.current.lastSeq, speed);
  }, [currentAuditId, open, speed]);

  const setSpeed = useCallback(
    (n: number) => {
      setSpeedState(n);
      if (playing && currentAuditId) open(currentAuditId, stateRef.current.lastSeq, n);
    },
    [playing, currentAuditId, open],
  );

  const reset = useCallback(() => {
    pause();
    setState(initialState);
    setCurrent(null);
  }, [pause]);

  const submitIdea = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      const found = pickAudit(audits, text);
      if (found) play(found.audit_id);
      else setState((s) => ({ ...s, errors: [...s.errors, noRecording(text, audits)] }));
    },
    [audits, play],
  );

  const dismissError = useCallback(() => setState((s) => ({ ...s, errors: [] })), []);

  return { state, audits, mode: "replay", speed, setSpeed, playing, play, pause, resume, reset, currentAuditId, submitIdea, dismissError };
}
