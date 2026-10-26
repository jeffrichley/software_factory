import { describe, expect, it } from "vitest";
import { inboxOf, resumeCommand } from "./inbox";

const row = (id: string, state: "Working" | "Needs you" | "Done" | "Stale", seen = false) => ({ id, state, seen });

describe("inboxOf", () => {
  it("splits out Needs you and unseen Done, keeping the server's order", () => {
    const sessions = [
      row("n2", "Needs you"),
      row("n1", "Needs you"),
      row("w", "Working"),
      row("d1", "Done"),
      row("seen", "Done", true),
      row("d2", "Done"),
      row("s", "Stale"),
    ];

    const { needs, doneUnseen } = inboxOf(sessions);

    expect(needs.map((s) => s.id)).toEqual(["n2", "n1"]);
    expect(doneUnseen.map((s) => s.id)).toEqual(["d1", "d2"]);
  });
});

describe("resumeCommand", () => {
  it("resumes the Claude Code session by its id", () => {
    expect(resumeCommand("0196viHB-a1")).toBe("claude --resume 0196viHB-a1");
  });
});
