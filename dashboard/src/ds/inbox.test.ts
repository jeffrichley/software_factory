import { describe, expect, it } from "vitest";
import { inboxOf, resumeCommand } from "./inbox";

const at = (state: "Working" | "Needs you" | "Done" | "Stale", since: string, seen = false, id = since) => ({
  id,
  state,
  state_since: `2026-10-26T12:${since}:00Z`,
  seen,
});

describe("inboxOf", () => {
  it("lists Needs you longest waiting first, and only unseen Done, latest first", () => {
    const sessions = [
      at("Working", "00"),
      at("Needs you", "05"),
      at("Done", "01"),
      at("Needs you", "02"),
      at("Done", "03", true),
      at("Done", "04"),
    ];

    const { needs, doneUnseen } = inboxOf(sessions);

    expect(needs.map((s) => s.id)).toEqual(["02", "05"]);
    expect(doneUnseen.map((s) => s.id)).toEqual(["04", "01"]);
  });
});

describe("resumeCommand", () => {
  it("resumes the Claude Code session by its id", () => {
    expect(resumeCommand("0196viHB-a1")).toBe("claude --resume 0196viHB-a1");
  });
});
