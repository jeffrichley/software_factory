import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { WayfinderView, type WayfinderViewProps } from "./WayfinderView";

afterEach(cleanup);

// The Map (React Flow) measures itself; jsdom has no layout.
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const props: WayfinderViewProps = {
  machine: "desk-win", repo: "jeff/widgets", kind: "Wayfinder", state: "Needs you", inStateMs: 60_000, now: null, actions: [],
  plan: { sessionId: "w", map: 50, ticket: 53, questions: ["Q1 - Layout"], created: [], closed: [] },
  map: {
    repo: "jeff/widgets", number: 50, title: "Chart the way", url: "#", destination: "A spec for the dashboard", fog: ["Sound"],
    tickets: [{ number: 53, title: "Prototype the dashboard", url: "#", state: "open", type: "prototype", mode: "AFK", assignees: [], gist: null, blockedBy: [] }],
  },
  needs: { reason: { kind: "hitl", ticket: "#53 Prototype the dashboard" }, session: "wf", terminal: null, resumeCommand: "claude --resume wf" },
};

describe("WayfinderView", () => {
  it("keeps the Destination and the Needs you block in a side column beside the Map", () => {
    render(<WayfinderView {...props} />);

    const side = screen.getByRole("complementary", { name: "This Wayfinder session" });
    expect(within(side).getByText("A spec for the dashboard")).toBeTruthy();
    expect(within(side).getByRole("region", { name: "Needs you" })).toBeTruthy();
    expect(screen.getAllByRole("region", { name: "Needs you" })).toHaveLength(1);
  });

  it("fits a wide Map to the width, and back to actual size", () => {
    render(<WayfinderView {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Fit to width" }));
    expect(screen.getByRole("button", { name: "Actual size" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Actual size" }));
    expect(screen.getByRole("button", { name: "Fit to width" })).toBeTruthy();
  });
});
