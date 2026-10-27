import { describe, expect, it } from "vitest";
import { selectedSessionOf } from "./selection";

const s = (id: string, kind: string, state: "Working" | "Needs you" | "Done" | "Stale", inStateMs: number) => ({ id, kind, state, inStateMs });
const job = (id: string, sessionId: string, stage = "In progress") => ({ id, sessionId, stage });

describe("selectedSessionOf", () => {
  const adhoc = s("a", "ad hoc", "Working", 5_000);
  const ticket = s("t", "Ticket Job", "Needs you", 60_000);
  const wayfinder = s("w", "Wayfinder", "Needs you", 30_000);
  const spec = s("p", "Spec Job", "Working", 600_000);

  it("keeps the session the human opened while it is on show", () => {
    expect(selectedSessionOf([adhoc, ticket, spec], [job("1", "p")], "a")?.id).toBe("a");
  });

  it("defaults to a Spec Job with an active Job", () => {
    expect(selectedSessionOf([adhoc, ticket, spec], [job("1", "p")], undefined)?.id).toBe("p");
  });

  it("passes over a Spec Job whose Job has ended, for the first Needs you", () => {
    expect(selectedSessionOf([adhoc, ticket, wayfinder, spec], [job("1", "p", "Merged")], undefined)?.id).toBe("t");
  });

  it("falls back to the most recently changed session when nothing needs you", () => {
    const older = s("o", "research", "Working", 90_000);
    expect(selectedSessionOf([older, adhoc], [], undefined)?.id).toBe("a");
  });

  it("falls back to the default when the opened session is no longer on show (its Machine hidden, or it ended)", () => {
    expect(selectedSessionOf([adhoc, ticket], [], "gone")?.id).toBe("t");
  });

  it("selects nothing when there are no sessions", () => {
    expect(selectedSessionOf([], [], "a")).toBeNull();
  });
});
