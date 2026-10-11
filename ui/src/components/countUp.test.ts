import { describe, it, expect } from "vitest";
import { countUp } from "./countUp";

describe("countUp", () => {
  it("jumps straight to the target when the duration is zero", () => {
    const frames: number[] = [];
    countUp(0, 42, 0, (v) => frames.push(v));
    expect(frames).toEqual([42]);
  });
  it("jumps straight to the target when requestAnimationFrame is unavailable", () => {
    const frames: number[] = [];
    const cancel = countUp(5, 10, 900, (v) => frames.push(v));
    expect(frames).toEqual([10]);
    expect(typeof cancel).toBe("function");
  });
});
