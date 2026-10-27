import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SpecJobView, type SpecJobViewProps } from "./SpecJobView";
import type { StepDetailData } from "../stepDetail";

afterEach(cleanup);

const EMPTY_DETAIL: StepDetailData = {
  phaseEvents: [], tests: null, files: [], commits: [], pr: null, review: null, checklist: null, struggle: null,
};

// The Ticket DAG (React Flow) measures itself; jsdom has no layout.
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const props: SpecJobViewProps = {
  machine: "wsl", repo: "jeff/widgets", kind: "Spec Job", state: "Working", inStateMs: 0, now: null, nowMs: 0, actions: [],
  job: {
    id: "1", sessionId: "s1", machine: "wsl", kind: "Spec Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", endedAt: null,
    duplicateOf: null, number: 4, workItem: { name: "#4 Widget export", url: "#" }, stage: "In progress", branch: null,
    worktree: null, pr: null,
  },
  steps: [
    { id: "10", number: 5, title: "Export schema", phase: "Red", phaseSince: "2026-10-26T12:00:00Z", blockedBy: [] },
    { id: "11", number: 6, title: "CSV writer", phase: "Pending", phaseSince: "2026-10-26T12:00:00Z", blockedBy: [5] },
  ],
};

describe("SpecJobView", () => {
  it("asks for a Ticket to be picked when opened on no Step", () => {
    render(<SpecJobView {...props} />);

    expect(screen.queryByRole("region", { name: "Step detail" })).toBeNull();
    expect(screen.getByText(/Select a Ticket in the DAG/)).toBeTruthy();
  });

  it("opens with the Step it was opened on (from its flow-strip chip) shown", () => {
    render(<SpecJobView {...props} stepId="10" />);

    const step = screen.getByRole("region", { name: "Step detail" });
    expect(step.querySelector("h3")?.textContent).toBe("#5 Export schema");
    expect(screen.queryByText(/Select a Ticket in the DAG/)).toBeNull();
  });

  describe("header and progress, as variant E", () => {
    const merged: SpecJobViewProps = {
      ...props,
      job: {
        ...props.job!, branch: "worktree-spec-4-widget-export", worktree: "/home/jeff/widgets/.claude/worktrees/spec-4",
        pr: { number: 60, url: "https://github.com/jeff/widgets/pull/60", draft: false },
        prTrack: [{ stage: "Draft", at: "2026-10-26T12:01:00Z" }, { stage: "Ready", at: "2026-10-26T12:03:00Z" }],
        prChecks: [{ name: "lint", status: "pass" }, { name: "e2e", status: "pending" }],
      },
      steps: [{ ...props.steps[0], phase: "Merged" }, props.steps[1]],
      details: { 10: { ...EMPTY_DETAIL, merge: { sha: "a41c9e2", at: "2026-10-26T12:02:00Z" } } },
    };
    const tile = (name: string) => screen.getByRole("group", { name }).textContent;

    it("shows four stat tiles: integration branch, Tickets merged, final code review and the Spec PR", () => {
      render(<SpecJobView {...merged} />);

      expect(tile("Integration branch")).toContain("worktree-spec-4-widget-export");
      expect(tile("Merged")).toContain("1 / 2 Tickets");
      expect(tile("Final code review")).toContain("Waiting");
      expect(tile("Spec PR")).toContain("#60 · Ready");
    });

    it("keeps the worktree and the PR link reachable", () => {
      render(<SpecJobView {...merged} />);

      expect(screen.getByText("/home/jeff/widgets/.claude/worktrees/spec-4")).toBeTruthy();
      expect(screen.getAllByRole("link", { name: /#60/ })[0].getAttribute("href")).toBe("https://github.com/jeff/widgets/pull/60");
    });

    it("lists each Ticket merged into the integration branch with its merge SHA, and how many are left", () => {
      render(<SpecJobView {...merged} />);

      const list = screen.getByRole("region", { name: "Merges into worktree-spec-4-widget-export" });
      expect(list.querySelector("li")?.textContent).toContain("#5 Export schema");
      expect(list.querySelector("li .sha")?.textContent).toBe("a41c9e2");
      expect(list.textContent).toContain("1 Ticket not yet merged.");
    });

    it("tracks the Spec PR Draft → Ready → Merged with its CI checks", () => {
      render(<SpecJobView {...merged} />);

      const track = screen.getByRole("list", { name: "PR state: Ready" });
      expect([...track.querySelectorAll("li")].map((li) => [li.textContent?.split(" ")[0], li.getAttribute("aria-current")])).toEqual([
        ["Draft", null], ["Ready", "step"], ["Merged", null],
      ]);
      expect(screen.getByText("e2e")).toBeTruthy();
    });
  });
});
