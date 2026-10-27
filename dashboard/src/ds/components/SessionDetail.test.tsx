import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdHocView, type AdHocViewProps } from "./SessionDetail";

afterEach(cleanup);

const base: AdHocViewProps = {
  machine: "mac-mini", repo: "jeff/worlds", kind: "ad hoc", state: "Working", inStateMs: 0, now: null, actions: [], unknownSkill: null,
};

describe("a session's detail header", () => {
  it("says why a Stale session can't be trusted, and when its Machine was last seen", () => {
    render(<AdHocView {...base} state="Stale" staleReason="Machine silent" machineSilentForMs={31 * 60_000} />);

    expect(screen.getByText(/Machine silent — mac-mini last seen 31m ago/)).toBeTruthy();
  });

  it("shows no stale note on a session that isn't Stale", () => {
    render(<AdHocView {...base} />);

    expect(screen.queryByText(/Machine silent/)).toBeNull();
  });

  it("shows why a waiting session Needs you, where it is, and copies its resume command", () => {
    const onCopy = vi.fn();
    render(
      <AdHocView
        {...base}
        state="Needs you"
        inStateMs={4 * 60_000}
        needs={{
          reason: { kind: "permission", tool: "Bash", command: "rm -rf .factory/tmp" }, session: "8c1f2e0a", terminal: null,
          resumeCommand: "claude --resume 8c1f2e0a-1111", onCopy,
        }}
      />,
    );

    const block = screen.getByRole("region", { name: "Needs you" });
    expect(block.textContent).toContain("Permission prompt");
    expect(block.textContent).toContain("waiting 4m");
    expect(block.textContent).toContain("rm -rf .factory/tmp");
    expect(block.textContent).toContain("8c1f2e0a");
    fireEvent.click(screen.getByRole("button", { name: /Copy resume command/ }));
    expect(onCopy).toHaveBeenCalledWith("claude --resume 8c1f2e0a-1111");
  });
});
