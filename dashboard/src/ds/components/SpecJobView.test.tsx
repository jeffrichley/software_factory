import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SpecJobView, type SpecJobViewProps } from "./SpecJobView";

afterEach(cleanup);

// The Ticket DAG (React Flow) measures itself; jsdom has no layout.
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const props: SpecJobViewProps = {
  machine: "wsl", repo: "jeff/widgets", kind: "Spec Job", state: "Working", inStateMs: 0, now: null, nowMs: 0, actions: [],
  job: {
    id: "1", sessionId: "s1", machine: "wsl", kind: "Spec Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z",
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
});
