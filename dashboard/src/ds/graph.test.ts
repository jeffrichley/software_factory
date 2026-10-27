import { describe, expect, it } from "vitest";
import { classifyGraph, fitZoom, layoutGraph, type GraphItem } from "./graph";

// A Spec: schema is merged; api waits on schema (now merged) and is blocked by auth; auth is open.
const spec: GraphItem[] = [
  { id: "schema", deps: [], resolved: true },
  { id: "auth", deps: [], resolved: false },
  { id: "api", deps: ["schema", "auth"], resolved: false, blockedBy: "auth" },
  { id: "ui", deps: ["api"], resolved: false },
];

describe("classifyGraph", () => {
  it("draws resolved, waiting and blocking edges", () => {
    expect(classifyGraph(spec).edges).toEqual([
      { id: "schema->api", from: "schema", to: "api", kind: "resolved" },
      { id: "auth->api", from: "auth", to: "api", kind: "blocking" },
      { id: "api->ui", from: "api", to: "ui", kind: "waiting" },
    ]);
  });

  it("marks unresolved items whose dependencies are all resolved as frontier", () => {
    expect(classifyGraph(spec).frontier).toEqual(["auth"]);
  });

  it("never puts a claimed item on the frontier", () => {
    const map: GraphItem[] = [
      { id: "a", deps: [], resolved: false, claimed: true },
      { id: "b", deps: [], resolved: false },
    ];
    expect(classifyGraph(map).frontier).toEqual(["b"]);
  });
});

describe("layoutGraph", () => {
  it("lays dependencies out left of what depends on them", () => {
    const pos = layoutGraph(spec, { width: 200, height: 80 });
    expect(pos.schema.x).toBeLessThan(pos.api.x);
    expect(pos.auth.x).toBeLessThan(pos.api.x);
    expect(pos.api.x).toBeLessThan(pos.ui.x);
  });

  it("stacks items with no dependency between them in one column without overlap", () => {
    const pos = layoutGraph(spec, { width: 200, height: 80 });
    expect(pos.schema.x).toBe(pos.auth.x);
    expect(Math.abs(pos.schema.y - pos.auth.y)).toBeGreaterThanOrEqual(80);
  });
});

describe("fitZoom", () => {
  it("shrinks a graph wider than its box to the box's width", () => {
    expect(fitZoom(2000, 1000)).toBe(0.5);
  });

  it("never enlarges a graph narrower than its box", () => {
    expect(fitZoom(600, 1000)).toBe(1);
  });

  it("leaves the graph 1:1 until the box has been measured", () => {
    expect(fitZoom(2000, 0)).toBe(1);
  });
});
