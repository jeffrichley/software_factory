import { describe, expect, it } from "vitest";
import { FLOW_COLUMNS, flowColumn, specInitials } from "./flow";

describe("flow strip columns", () => {
  it("runs from Phase unknown through the Phases to Planning / ad hoc", () => {
    expect(FLOW_COLUMNS).toEqual([
      "Phase unknown", "Exploring", "Red", "Green", "Refactor", "Reviewing", "Committed", "Merged", "Planning / ad hoc",
    ]);
  });

  it("puts a Step in its Phase's column, an unknown Phase first, and planning sessions last", () => {
    expect(FLOW_COLUMNS[flowColumn({ phase: "Green" })]).toBe("Green");
    expect(flowColumn({ phase: null })).toBe(0);
    expect(flowColumn("planning")).toBe(8);
  });
});

describe("specInitials", () => {
  it("abbreviates a Spec's name to two letters for its chips", () => {
    expect(specInitials("order export pipeline")).toBe("OE");
    expect(specInitials("Factory")).toBe("F");
  });
});
