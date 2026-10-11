import { describe, it, expect } from "vitest";
import { displayIdea, isSynthetic, noRecording, pickAudit } from "./useAudit";

const real = { audit_id: "20261012-1", idea: "buy dips in an uptrend", started_at: "2026-10-12T09:00:00Z", finished: true };
const synth = { audit_id: "synthetic-demo", idea: "SYNTHETIC FIXTURE: buy dips in an uptrend (not a real audit)", started_at: "2026-10-11T12:00:00Z", finished: true };

describe("isSynthetic", () => {
  it("flags the fixture prefix only", () => {
    expect(isSynthetic(synth.idea)).toBe(true);
    expect(isSynthetic(real.idea)).toBe(false);
    expect(isSynthetic("")).toBe(false);
  });
});

describe("pickAudit", () => {
  it("prefers a real recording over the synthetic fixture whatever the order", () => {
    expect(pickAudit([synth, real], "buy dips in an uptrend")?.audit_id).toBe(real.audit_id);
    expect(pickAudit([real, synth], "buy dips in an uptrend")?.audit_id).toBe(real.audit_id);
  });
  it("falls back to the fixture when nothing real matches", () => {
    expect(pickAudit([synth], "buy dips in an uptrend")?.audit_id).toBe(synth.audit_id);
  });
  it("matches the whole idea only, ignoring case and spacing", () => {
    expect(pickAudit([real], "  Buy Dips  in an UPTREND ")?.audit_id).toBe(real.audit_id);
    expect(pickAudit([real, synth], "buy dips")).toBeNull();
    expect(pickAudit([real, synth], "buy")).toBeNull();
    expect(pickAudit([real, synth], "buy dips in an uptrend on Mondays")).toBeNull();
  });
  it("returns null for no match or a too-short query", () => {
    expect(pickAudit([real, synth], "straddles")).toBeNull();
    expect(pickAudit([real, synth], "a")).toBeNull();
  });
});

describe("displayIdea and noRecording", () => {
  it("strips the fixture's label wrapper and leaves real ideas alone", () => {
    expect(displayIdea(synth.idea)).toBe("buy dips in an uptrend");
    expect(displayIdea(real.idea)).toBe("buy dips in an uptrend");
  });
  it("names the recorded ideas once each, or says how to record one", () => {
    expect(noRecording("buy gold", [real, synth])).toBe('No recording of "buy gold". Recorded ideas: buy dips in an uptrend.');
    expect(noRecording("buy gold", [])).toMatch(/^No recordings yet/);
  });
});

describe("runLabel", () => {
  it("names synthetic fixtures and fake-LLM runs, nothing for a real run", async () => {
    const { runLabel } = await import("./useAudit");
    expect(runLabel("SYNTHETIC FIXTURE: x", "fake")).toBe("SYNTHETIC · NOT A REAL AUDIT");
    expect(runLabel("buy dips", "fake")).toBe("FAKE LLM · KEYWORD PLANNER, REAL DATA");
    expect(runLabel("buy dips", "deepseek")).toBeNull();
    expect(runLabel("buy dips", null)).toBeNull();
  });
});
