import { describe, it, expect } from "vitest";
import { toSeries } from "./equitySeries";

describe("toSeries", () => {
  it("returns an empty list for no points", () => {
    expect(toSeries([])).toEqual([]);
  });
  it("sorts ascending by date", () => {
    expect(toSeries([["2025-01-03", 2], ["2025-01-02", 1]])).toEqual([{ time: "2025-01-02", value: 1 }, { time: "2025-01-03", value: 2 }]);
  });
  it("drops malformed dates and non-finite values", () => {
    expect(toSeries([["bad", 1], ["2025-01-02", NaN], ["2025-01-03", Infinity], ["2025-01-04", 0.5]])).toEqual([{ time: "2025-01-04", value: 0.5 }]);
  });
  it("keeps the last value for a duplicate date", () => {
    expect(toSeries([["2025-01-02", 1], ["2025-01-02", 3]])).toEqual([{ time: "2025-01-02", value: 3 }]);
  });
});
