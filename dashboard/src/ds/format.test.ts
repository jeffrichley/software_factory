import { describe, expect, it } from "vitest";
import { formatAgo, formatClock, formatDuration, phaseClass, repoName, stateLook } from "./format";

describe("formatDuration", () => {
  it("shows seconds under a minute, minutes under an hour, then hours and minutes", () => {
    expect(formatDuration(42_000)).toBe("42s");
    expect(formatDuration(7 * 60_000 + 5_000)).toBe("7m");
    expect(formatDuration(2 * 3_600_000 + 14 * 60_000)).toBe("2h 14m");
  });
});

describe("stateLook", () => {
  it("labels unseen Done so it stands out from seen Done", () => {
    expect(stateLook("Done", false)).toEqual({ tone: "done", label: "Done · unseen" });
    expect(stateLook("Done", true)).toEqual({ tone: "done-seen", label: "Done" });
  });

  it("gives Needs you, Working and Stale their own tones", () => {
    expect(stateLook("Needs you")).toEqual({ tone: "needs", label: "Needs you" });
    expect(stateLook("Working")).toEqual({ tone: "working", label: "Working" });
    expect(stateLook("Stale")).toEqual({ tone: "stale", label: "Stale" });
  });

  it("says why a session is Stale", () => {
    expect(stateLook("Stale", false, "Machine silent")).toEqual({ tone: "stale", label: "Stale · Machine silent" });
  });

  it("says how long a quiet Working session has had no events, keeping it Working", () => {
    expect(stateLook("Working", false, undefined, 23 * 60_000 + 10_000)).toEqual({ tone: "working", label: "Working · quiet 23m" });
    expect(stateLook("Working", false, undefined, 2 * 3_600_000 + 5 * 60_000)).toEqual({ tone: "working", label: "Working · quiet 2h 5m" });
  });
});

describe("phaseClass", () => {
  it("names the CSS class for a Phase, an unknown Phase and a planning session", () => {
    expect(phaseClass("Red")).toBe("ph-red");
    expect(phaseClass(null)).toBe("ph-unknown");
    expect(phaseClass("planning")).toBe("fplan");
  });
});

describe("formatClock", () => {
  it("shows a timeline time as local hours and minutes", () => {
    expect(formatClock(new Date(2026, 9, 26, 9, 5, 42).toISOString())).toBe("09:05");
    expect(formatClock(new Date(2026, 9, 26, 23, 59).toISOString())).toBe("23:59");
  });
});

describe("repoName", () => {
  it("shows a repo by its bare name, leaving out the owner", () => {
    expect(repoName("jeffrichley/software_factory")).toBe("software_factory");
    expect(repoName("widgets")).toBe("widgets");
  });
});

describe("formatAgo", () => {
  it("says how long ago, in days once it is a day or more", () => {
    expect(formatAgo(3 * 3_600_000 + 10 * 60_000)).toBe("3h 10m ago");
    expect(formatAgo(26 * 3_600_000)).toBe("1d ago");
    expect(formatAgo(45_000)).toBe("45s ago");
  });
});
