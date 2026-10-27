import { describe, expect, it } from "vitest";
import { formatOffset, replayFrame, replayLength, type ReplayData } from "./replay";

const ev = (t: number, kind: string, text: string, step_id: string | null = null, phase: string | null = null) => ({
  t, at: "", kind, text, step_id, phase,
});

const REPLAY: ReplayData = {
  job_id: "3",
  started_at: "2026-10-26T12:00:00Z",
  ended_at: "2026-10-26T12:10:00Z",
  steps: [{ id: "7", number: 5, title: "Add the widget API!" }],
  events: [
    ev(0, "start", "Job started: #5"),
    ev(30, "phase", "#5 Exploring", "7", "Exploring"),
    ev(90, "phase", "#5 Red", "7", "Red"),
    ev(120, "test_fail", "Tests fail: pytest"),
    ev(200, "phase", "#5 Green", "7", "Green"),
  ],
};

describe("replayFrame", () => {
  it("before any Phase change, each Step's Phase is unknown and the current event is the Job's start", () => {
    expect(replayFrame(REPLAY, 10)).toEqual({ phases: { "7": null }, current: 0 });
  });

  it("at a time, each Step is in the Phase it last changed to, and the current event is the last one reached", () => {
    expect(replayFrame(REPLAY, 150)).toEqual({ phases: { "7": "Red" }, current: 3 });
    expect(replayFrame(REPLAY, 200)).toEqual({ phases: { "7": "Green" }, current: 4 });
  });

  it("before the first event there is no current event", () => {
    expect(replayFrame({ ...REPLAY, events: REPLAY.events.slice(1) }, 0).current).toBe(-1);
  });
});

describe("replayLength", () => {
  it("runs from the Job's start to its end", () => {
    expect(replayLength(REPLAY)).toBe(600);
  });

  it("runs to the last event while the Job has no end", () => {
    expect(replayLength({ ...REPLAY, ended_at: null })).toBe(200);
  });

  it("is never zero, so the scrubber has somewhere to go", () => {
    expect(replayLength({ ...REPLAY, ended_at: null, events: [ev(0, "start", "Job started")] })).toBe(1);
  });
});

describe("formatOffset", () => {
  it("shows time since the Job started as m:ss, or h:mm:ss past an hour", () => {
    expect([0, 65, 600, 3725].map(formatOffset)).toEqual(["0:00", "1:05", "10:00", "1:02:05"]);
  });
});
