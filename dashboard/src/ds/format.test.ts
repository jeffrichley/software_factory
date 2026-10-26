import { describe, expect, it } from "vitest";
import { formatDuration, stateLook } from "./format";

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
});
