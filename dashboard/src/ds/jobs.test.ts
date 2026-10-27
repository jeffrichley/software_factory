import { describe, expect, it } from "vitest";
import { currentJob, endedJob, historyOf, isEnded } from "./jobs";

describe("currentJob", () => {
  it("is the session's latest started Job, by numeric id", () => {
    const jobs = [
      { id: "9", sessionId: "1" },
      { id: "10", sessionId: "1" },
      { id: "11", sessionId: "2" },
    ];
    expect(currentJob(jobs, "1")?.id).toBe("10");
  });

  it("is null for a session with no Job", () => {
    expect(currentJob([{ id: "1", sessionId: "2" }], "1")).toBeNull();
  });
});

describe("historyOf", () => {
  it("is the Merged, Closed and Abandoned Jobs, latest started first", () => {
    const jobs = [
      { id: "1", stage: "Merged" },
      { id: "2", stage: "PR open" },
      { id: "3", stage: "Abandoned" },
      { id: "10", stage: "Closed" },
      { id: "11", stage: "In progress" },
    ];
    expect(historyOf(jobs).map((j) => j.id)).toEqual(["10", "3", "1"]);
  });
});

describe("isEnded", () => {
  it("is true only for the stages that move a Job to History", () => {
    expect(["In progress", "PR open", "Merged", "Closed", "Abandoned"].map(isEnded)).toEqual([false, false, true, true, true]);
  });
});

describe("historyOf with the Machine filter", () => {
  it("leaves out Jobs on hidden Machines", () => {
    const jobs = [
      { id: "1", stage: "Merged", machine: "wsl" },
      { id: "2", stage: "Merged", machine: "mac" },
    ];
    expect(historyOf(jobs, ["mac"]).map((j) => j.id)).toEqual(["1"]);
  });
});

describe("endedJob", () => {
  const now = Date.parse("2026-10-27T15:00:00Z");

  it("says how a Job ended, how long it took and how long ago, as variant E's History rows do", () => {
    expect(endedJob({ stage: "Merged", startedAt: "2026-10-27T10:38:00Z", endedAt: "2026-10-27T11:50:00Z" }, now)).toEqual({
      outcome: "PR merged", icon: "check", tone: "merged", took: "1h 12m", ago: "3h 10m ago",
    });
    expect(endedJob({ stage: "Closed", startedAt: "2026-10-26T10:00:00Z", endedAt: "2026-10-26T10:54:00Z" }, now)).toMatchObject({
      outcome: "PR closed", icon: "x", took: "54m", ago: "1d ago",
    });
    expect(endedJob({ stage: "Abandoned", startedAt: "2026-10-27T14:00:00Z", endedAt: "2026-10-27T14:26:00Z" }, now).outcome).toBe("Abandoned");
  });

  it("leaves how long it took and when it ended unknown until the server has seen it end", () => {
    expect(endedJob({ stage: "Merged", startedAt: "2026-10-27T10:38:00Z", endedAt: null }, now)).toMatchObject({ took: null, ago: null });
  });
});
