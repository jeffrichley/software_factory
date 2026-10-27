import { describe, expect, it } from "vitest";
import { mergesOf, prTrack } from "./specJob";
import type { SpecStepData } from "./specDag";

const PR = { number: 60, url: "https://github.com/jeff/widgets/pull/60", draft: true };

describe("prTrack", () => {
  it("walks Draft → Ready → Merged, marking the stages reached with when and the latest as current", () => {
    const track = prTrack({ ...PR, draft: false }, [
      { stage: "Draft", at: "2026-10-26T12:01:00Z" },
      { stage: "Ready", at: "2026-10-26T12:03:00Z" },
    ]);

    expect(track).toEqual([
      { stage: "Draft", at: "2026-10-26T12:01:00Z", status: "done" },
      { stage: "Ready", at: "2026-10-26T12:03:00Z", status: "current" },
      { stage: "Merged", at: null, status: "todo" },
    ]);
  });

  it("before the poll has seen the PR, places it by its draft flag, with no times", () => {
    expect(prTrack(PR, []).map((s) => [s.stage, s.status, s.at])).toEqual([
      ["Draft", "current", null], ["Ready", "todo", null], ["Merged", "todo", null],
    ]);
    expect(prTrack({ ...PR, draft: false }, []).map((s) => s.status)).toEqual(["done", "current", "todo"]);
  });

  it("ends at Closed instead of Merged for a PR closed without merging", () => {
    const track = prTrack(PR, [{ stage: "Ready", at: "2026-10-26T12:03:00Z" }, { stage: "Closed", at: "2026-10-26T12:09:00Z" }]);

    expect(track.map((s) => [s.stage, s.status, s.at])).toEqual([
      ["Draft", "done", null], ["Ready", "done", "2026-10-26T12:03:00Z"], ["Closed", "current", "2026-10-26T12:09:00Z"],
    ]);
  });
});

describe("mergesOf", () => {
  const step = (id: string, number: number, phase: SpecStepData["phase"]): SpecStepData => ({
    id, number, title: `Ticket ${number}`, phase, phaseSince: "2026-10-26T12:00:00Z", blockedBy: [],
  });

  it("lists each Step merged into the integration branch in merge order, with its SHA when known", () => {
    const steps = [step("1", 5, "Merged"), step("2", 6, "Merged"), step("3", 7, "Green")];
    const merges = mergesOf(steps, {
      1: { sha: null, at: "2026-10-26T12:20:00Z" },
      2: { sha: "a41c9e2", at: "2026-10-26T12:10:00Z" },
    });

    expect(merges.map((m) => [m.step.id, m.sha, m.at])).toEqual([["2", "a41c9e2", "2026-10-26T12:10:00Z"], ["1", null, "2026-10-26T12:20:00Z"]]);
  });

  it("keeps a Step that reached Merged without a merge seen (e.g. by its PR merging), unknown, after the others", () => {
    const merges = mergesOf([step("1", 5, "Merged"), step("2", 6, "Merged")], { 2: { sha: "a41c9e2", at: "2026-10-26T12:10:00Z" } });

    expect(merges.map((m) => [m.step.id, m.sha, m.at])).toEqual([["2", "a41c9e2", "2026-10-26T12:10:00Z"], ["1", null, null]]);
  });
});
