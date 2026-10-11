// Server-Sent Events client for /api/audits/{id}/events, plus the two small fetches.
import type { AuditEvent, AuditSummary } from "./events";

export interface StreamOptions {
  replay: boolean;
  speed: number;
  from: number;
  onEvent: (e: AuditEvent) => void;
  onEnd: () => void;
  onError: (msg: string) => void;
}

/** Open the event stream; returns a close function. The server sends `event: end` when done. */
export function openEvents(auditId: string, opts: StreamOptions): () => void {
  const q = new URLSearchParams({ speed: String(opts.speed), from: String(opts.from) });
  if (opts.replay) q.set("replay", "1");
  const es = new EventSource(`/api/audits/${encodeURIComponent(auditId)}/events?${q}`);
  let closed = false;
  const close = () => {
    if (!closed) {
      closed = true;
      es.close();
    }
  };
  es.onmessage = (m) => {
    try {
      opts.onEvent(JSON.parse(m.data) as AuditEvent);
    } catch {
      opts.onError("unreadable event line");
    }
  };
  es.addEventListener("end", () => {
    close();
    opts.onEnd();
  });
  es.onerror = () => {
    if (closed) return;
    close();
    opts.onError("The event stream was lost. Is the server still running? Press Play to continue from where it stopped.");
  };
  return close;
}

export async function listAudits(): Promise<AuditSummary[]> {
  const r = await fetch("/api/audits");
  if (!r.ok) throw new Error(`list failed: ${r.status}`);
  return (await r.json()) as AuditSummary[];
}

export async function fetchReport(auditId: string): Promise<string> {
  const r = await fetch(`/api/audits/${encodeURIComponent(auditId)}/report`);
  if (!r.ok) throw new Error(`report failed: ${r.status}`);
  return r.text();
}
