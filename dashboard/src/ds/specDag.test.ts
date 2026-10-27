import { describe, expect, it } from "vitest";
import { classifyGraph } from "./graph";
import { specGraph, type SpecStepData } from "./specDag";

const NOW = Date.parse("2026-10-26T12:10:00Z");
const step = (id: string, number: number, over: Partial<SpecStepData> = {}): SpecStepData => ({
  id, number, title: `Ticket ${number}`, phase: "Pending", phaseSince: "2026-10-26T12:00:00Z", blockedBy: [], ...over,
});

describe("specGraph", () => {
  it("draws one node per Step, named by its Ticket, with its Phase and time in it", () => {
    const [node] = specGraph([step("1", 5, { title: "Export schema", phase: "Red" })], NOW);

    expect(node).toMatchObject({ id: "1", deps: [], resolved: false, body: { kind: "step", ticket: "#5 Export schema", phase: "Red", phaseForMs: 600_000 } });
  });

  it("joins each Step to the Steps of the Tickets that block it, ignoring blockers outside the Spec", () => {
    const nodes = specGraph([step("1", 5), step("2", 6, { blockedBy: [5, 99] })], NOW);

    expect(nodes.map((n) => [n.id, n.deps])).toEqual([["1", []], ["2", ["1"]]]);
  });

  it("resolves a merged Step; a started Step on an unmerged Ticket is blocked by it, a Pending one only waits", () => {
    const nodes = specGraph([
      step("1", 5, { phase: "Merged" }),
      step("2", 6, { phase: "Green" }),
      step("3", 7, { phase: "Red", blockedBy: [5, 6] }),
      step("4", 8, { blockedBy: [6] }),
    ], NOW);

    expect(classifyGraph(nodes).edges.map((e) => [e.id, e.kind])).toEqual([
      ["1->3", "resolved"], ["2->3", "blocking"], ["2->4", "waiting"],
    ]);
  });

  it("puts only Pending Steps whose blockers are all merged on the frontier", () => {
    const nodes = specGraph([
      step("1", 5, { phase: "Merged" }),
      step("2", 6, { blockedBy: [5] }),
      step("3", 7, { phase: null }),
      step("4", 8, { blockedBy: [7] }),
    ], NOW);

    expect(classifyGraph(nodes).frontier).toEqual(["2"]);
  });

  it("names a Step without a known title by its number, or Ticket unknown", () => {
    const nodes = specGraph([step("1", 5, { title: null }), { ...step("2", 0), number: null }], NOW);

    expect(nodes.map((n) => n.body.kind === "step" && n.body.ticket)).toEqual(["#5", "Ticket unknown"]);
  });
});
