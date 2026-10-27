import { describe, expect, it } from "vitest";
import { FLOW_COLUMNS, flowColumn, flowRows, specInitials, type FlowSession, type FlowStepData } from "./flow";

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

describe("flowRows", () => {
  const session = (id: string, over: Partial<FlowSession> = {}): FlowSession => ({
    id, machine: "wsl", repo: "jeff/widgets", state: "Working", seen: false, kind: "Ticket Job", ...over,
  });
  const step = (id: string, sessionId: string, jobId: string, over: Partial<FlowStepData> = {}): FlowStepData => ({
    id, jobId, sessionId, repo: "jeff/widgets", number: 5, title: "Add the widget API", phase: "Red", ...over,
  });
  const jobs = [{ id: "1", sessionId: "s1" }, { id: "2", sessionId: "s1" }, { id: "3", sessionId: "s2" }];

  it("gives each Tracked repo a row, empty when nothing runs there", () => {
    expect(flowRows(["jeff/widgets", "jeff/gadgets"], [], [], [])).toEqual([
      { repo: "jeff/widgets", chips: [] },
      { repo: "jeff/gadgets", chips: [] },
    ]);
  });

  it("puts one chip per Step of each session's current Job, coloured by its session and in its Phase", () => {
    const [row] = flowRows(
      ["jeff/widgets"],
      [session("s1", { state: "Needs you", machine: "mac" })],
      jobs,
      [step("10", "s1", "1", { phase: "Committed" }), step("11", "s1", "2", { phase: "Red" })],
    );

    expect(row.chips).toEqual([{
      id: "step-11", sessionId: "s1", label: "Add the widget API", name: "#5 Add the widget API",
      state: "Needs you", seen: false, phase: "Red", machine: "mac", repo: "jeff/widgets",
    }]);
  });

  it("names a Step by its Ticket number until its title is known, and Ticket unknown without one", () => {
    const [row] = flowRows(
      ["jeff/widgets"],
      [session("s1"), session("s2")],
      jobs,
      [step("11", "s1", "2", { title: null, phase: null }), step("12", "s2", "3", { number: null, title: null })],
    );

    expect(row.chips.map((c) => [c.label, c.name, c.phase])).toEqual([
      ["#5", "#5", null],
      ["Ticket unknown", "Ticket unknown", "Red"],
    ]);
  });

  it("puts sessions with no Job in Planning / ad hoc, by kind", () => {
    const [row] = flowRows(
      ["jeff/widgets"],
      [session("w", { kind: "Wayfinder" }), session("r", { kind: "research", state: "Done", seen: true }), session("a", { kind: "ad hoc" })],
      [],
      [],
    );

    expect(row.chips.map((c) => [c.id, c.label, c.phase, c.planIcon, c.state, c.seen])).toEqual([
      ["session-w", "Wayfinder", "planning", "flag", "Working", false],
      ["session-r", "research", "planning", "search", "Done", true],
      ["session-a", "ad hoc", "planning", "terminal", "Working", false],
    ]);
  });

  it("shows a Job session with no Steps yet as Phase unknown", () => {
    const [row] = flowRows(["jeff/widgets"], [session("s2", { kind: "Spec Job" })], jobs, []);

    expect(row.chips.map((c) => [c.id, c.label, c.phase])).toEqual([["session-s2", "Spec Job", null]]);
  });

  it("leaves out Steps of sessions it isn't shown, and sessions of repos without a row", () => {
    const rows = flowRows(["jeff/widgets"], [session("x", { repo: "jeff/other", kind: "ad hoc" })], jobs, [step("11", "s1", "2")]);

    expect(rows).toEqual([{ repo: "jeff/widgets", chips: [] }]);
  });

  it("carries a Stale session's reason onto its chips", () => {
    const [row] = flowRows(["jeff/widgets"], [session("s1", { state: "Stale", staleReason: "Machine silent" })], jobs, [step("11", "s1", "2")]);

    expect(row.chips[0].staleReason).toBe("Machine silent");
  });
});

describe("specInitials", () => {
  it("abbreviates a Spec's name to two letters for its chips", () => {
    expect(specInitials("order export pipeline")).toBe("OE");
    expect(specInitials("Factory")).toBe("F");
  });
});
