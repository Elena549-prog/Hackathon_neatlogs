// Replay session: which audit plays, at what speed, paused or not. Live mode is stretch (spec 17).
import { useCallback, useEffect, useRef, useState } from "react";
import type { AuditSummary } from "./events";
import { initialState, reduce, type UiState } from "./state";
import { listAudits, openEvents } from "./stream";

export const NO_RECORDING = "No recording for this idea. Record one with the auditor first.";

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
      const t = text.trim().toLowerCase();
      if (!t) return;
      const found = audits.find((a) => {
        const i = a.idea.toLowerCase();
        return i.includes(t) || t.includes(i);
      });
      if (found) play(found.audit_id);
      else setState((s) => ({ ...s, errors: [...s.errors, NO_RECORDING] }));
    },
    [audits, play],
  );

  return { state, audits, mode: "replay", speed, setSpeed, playing, play, pause, resume, reset, currentAuditId, submitIdea };
}
