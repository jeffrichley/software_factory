import { describe, expect, it } from "vitest";
import { filterUrl, hiddenMachinesOf, viewOf } from "./machineFilter";

const names = ["mac", "wsl", "win"];

describe("hiddenMachinesOf", () => {
  it("hides the Machines ?machines= leaves out, ignoring what the browser remembers", () => {
    expect(hiddenMachinesOf(names, "?machines=mac,wsl", ["mac"])).toEqual(["win"]);
  });

  it("falls back to the Machines the browser remembers hiding, among those that exist", () => {
    expect(hiddenMachinesOf(names, "", ["win", "gone"])).toEqual(["win"]);
  });

  it("shows every Machine by default", () => {
    expect(hiddenMachinesOf(names, "?variant=E", [])).toEqual([]);
  });
});

describe("filterUrl", () => {
  it("names the Machines shown in ?machines=, keeping other parameters", () => {
    expect(filterUrl("http://mac.local:47821/?x=1", names, ["wsl"])).toBe("http://mac.local:47821/?x=1&machines=mac%2Cwin");
  });

  it("drops ?machines= when nothing is hidden", () => {
    expect(filterUrl("http://mac.local:47821/?machines=mac", names, [])).toBe("http://mac.local:47821/");
  });
});

const s = (id: string, machine: string, state: "Working" | "Needs you" | "Done" | "Stale", hidden = false) =>
  ({ id, machine, state, hidden });

describe("viewOf", () => {
  const sessions = [
    s("a", "mac", "Needs you"),
    s("b", "win", "Needs you"),
    s("c", "win", "Working"),
    s("d", "wsl", "Needs you", true),
    s("e", "win", "Needs you", true),
    s("f", "mac", "Done", true),
  ];

  it("shows only shown sessions on shown Machines", () => {
    expect(viewOf(sessions, ["win"]).shown.map((x) => x.id)).toEqual(["a"]);
  });

  it("counts Needs you on hidden Machines, but never from hidden sessions", () => {
    expect(viewOf(sessions, ["win", "wsl"]).hiddenNeeds.map((x) => x.id)).toEqual(["b"]);
  });

  it("lists hidden sessions on shown Machines so they can be shown again", () => {
    expect(viewOf(sessions, ["win"]).hiddenSessions.map((x) => x.id)).toEqual(["d", "f"]);
  });
});
