// Replay session: which audit plays, at what speed, paused or not. Live mode is stretch (spec 17).
import { useCallback, useEffect, useRef, useState } from "react";
import type { AuditSummary } from "./events";
import { initialState, reduce, type UiState } from "./state";
import { listAudits, openEvents } from "./stream";

export const NO_RECORDING = "No recording for this idea. Record one with the auditor first.";
const SYNTHETIC_PREFIX = "SYNTHETIC FIXTURE";
const MIN_QUERY = 3;

/** The development fixture labels itself through its idea text (scripts/synthetic_audit.py). */
export const isSynthetic = (idea: string): boolean => idea.startsWith(SYNTHETIC_PREFIX);

/** Honesty label for the command bar and the stamp: synthetic fixture, fake-LLM run, or none for a real run. */
export function runLabel(idea: string, provider: string | null): string | null {
  if (isSynthetic(idea)) return "SYNTHETIC · NOT A REAL AUDIT";
  if (provider === "fake") return "FAKE LLM · KEYWORD PLANNER, REAL DATA";
  return null;
}

/** The recording to play for a typed idea or chip: a real recording wins over the synthetic fixture. */
export function pickAudit(audits: AuditSummary[], text: string): AuditSummary | null {
  const t = text.trim().toLowerCase();
  if (t.length < MIN_QUERY) return null;
  const matches = audits.filter((a) => {
    const i = a.idea.toLowerCase();
    return i.includes(t) || t.includes(i);
  });
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
    listAudits().then(setAudits).catch(() => setAudits([]));
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
      else setState((s) => ({ ...s, errors: [...s.errors, NO_RECORDING] }));
    },
    [audits, play],
  );

  return { state, audits, mode: "replay", speed, setSpeed, playing, play, pause, resume, reset, currentAuditId, submitIdea };
}
