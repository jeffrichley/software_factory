import { describe, expect, it } from "vitest";
import { classifyGraph } from "./graph";
import { outlineProgress, ticketsGraph, type CreatedTicketData } from "./planning";

const t = (number: number, over: Partial<CreatedTicketData> = {}): CreatedTicketData => ({
  number, title: `Ticket ${number}`, url: `https://github.com/jeff/widgets/issues/${number}`, state: "open", blockedBy: [], ...over,
});

describe("ticketsGraph", () => {
  it("draws each created Ticket as not started, named by number and title", () => {
    const nodes = ticketsGraph([t(13, { title: "Export one table" }), t(14, { title: null })]);

    expect(nodes.map((n) => [n.id, n.resolved, n.body])).toEqual([
      ["13", false, { kind: "ticket", name: "#13 Export one table" }],
      ["14", false, { kind: "ticket", name: "#14" }],
    ]);
  });

  it("joins each Ticket to the created Tickets that block it, so only unblocked ones are frontier", () => {
    const nodes = ticketsGraph([t(13), t(14, { blockedBy: [13, 2] }), t(15, { blockedBy: [13, 14] })]);

    expect(nodes.map((n) => [n.id, n.deps])).toEqual([["13", []], ["14", ["13"]], ["15", ["13", "14"]]]);
    expect(classifyGraph(nodes).frontier).toEqual(["13"]);
  });
});

describe("outlineProgress", () => {
  it("counts the sections written and points at the first one still to write", () => {
    const outline = [
      { section: "Problem Statement", written: true },
      { section: "Solution", written: true },
      { section: "User Stories", written: false },
      { section: "Out of Scope", written: true },
    ];

    expect(outlineProgress(outline)).toEqual({ written: 3, total: 4, current: 2 });
  });

  it("has no current section once every one is written", () => {
    expect(outlineProgress([{ section: "Solution", written: true }]).current).toBeNull();
  });
});
