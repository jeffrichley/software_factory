import { describe, expect, it } from "vitest";
import { classifyGraph } from "./graph";
import { mapGraph, decisionName, type DecisionTicketData, type MapData } from "./wayfinder";

const TITLES: Record<number, string> = { 2: "Pick the export format", 3: "Choose the columns", 4: "Prototype the download", 5: "Name the file" };
const t = (number: number, over: Partial<DecisionTicketData> = {}): DecisionTicketData => ({
  number, title: TITLES[number] ?? "Untitled decision", url: `https://github.com/jeff/widgets/issues/${number}`, state: "open",
  type: "grilling", mode: "HITL", assignees: [], gist: null, blockedBy: [], ...over,
});
const map = (tickets: DecisionTicketData[]): MapData => ({
  repo: "jeff/widgets", number: 1, title: "Widgets", url: "#", destination: "A spec", fog: [], tickets,
});

describe("mapGraph", () => {
  it("draws each Decision ticket with its type, HITL/AFK and open, claimed or closed with its gist", () => {
    const nodes = mapGraph(map([
      t(2, { state: "closed", type: "research", mode: "AFK", gist: "CSV first" }),
      t(3, { assignees: ["jeffrichley"] }),
      t(4, { type: "prototype" }),
    ]), { ticket: null, needs: false });

    expect(nodes.map((n) => [n.id, n.resolved, n.claimed, n.muted, n.body])).toEqual([
      ["2", true, false, true, { kind: "decision", name: "#2 Pick the export format", type: "research", mode: "AFK", status: { state: "closed", gist: "CSV first" }, needs: false }],
      ["3", false, true, false, { kind: "decision", name: "#3 Choose the columns", type: "grilling", mode: "HITL", status: { state: "claimed", by: "jeffrichley" }, needs: false }],
      ["4", false, false, false, { kind: "decision", name: "#4 Prototype the download", type: "prototype", mode: "HITL", status: { state: "open" }, needs: false }],
    ]);
  });

  it("marks the ticket this session works as claimed by it, and as needing you while it waits", () => {
    const [node] = mapGraph(map([t(3)]), { ticket: 3, needs: true });

    expect(node.claimed).toBe(true);
    expect(node.body).toMatchObject({ status: { state: "claimed", by: "this session" }, needs: true });
  });

  it("shows a closed ticket's missing gist and an unknown type or mode as unknown", () => {
    const [node] = mapGraph(map([t(2, { state: "closed", type: null, mode: null })]), { ticket: null, needs: false });

    expect(node.body).toMatchObject({ type: "type unknown", mode: "—", status: { state: "closed", gist: "—" } });
  });

  it("joins tickets to their blockers on the Map; a claimed ticket on an open blocker is blocked by it", () => {
    const nodes = mapGraph(map([
      t(2, { state: "closed" }),
      t(3),
      t(4, { blockedBy: [2, 3, 99] }),
      t(5, { blockedBy: [3], assignees: ["jeffrichley"] }),
    ]), { ticket: null, needs: false });

    const { edges, frontier } = classifyGraph(nodes);
    expect(edges.map((e) => [e.id, e.kind])).toEqual([["2->4", "resolved"], ["3->4", "waiting"], ["3->5", "blocking"]]);
    expect(frontier).toEqual(["3"]);
    expect(nodes[3].body).toMatchObject({ blockedByName: "#3 Choose the columns" });
  });
});

describe("decisionName", () => {
  it("names a ticket by its number and title", () => {
    expect(decisionName(t(3, { title: "Choose the columns" }))).toBe("#3 Choose the columns");
  });
});
