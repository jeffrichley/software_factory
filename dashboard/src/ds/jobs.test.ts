import { describe, expect, it } from "vitest";
import { currentJob } from "./jobs";

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
