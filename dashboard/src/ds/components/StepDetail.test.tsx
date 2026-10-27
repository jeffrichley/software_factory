import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { StepDetailData } from "../stepDetail";
import { StepDetail } from "./StepDetail";

afterEach(cleanup);

const detail: StepDetailData = {
  phaseEvents: [], tests: null, commits: [], pr: null, review: null, checklist: null, struggle: null,
  files: [
    { path: "src/api.py", edits: 3, added: 42, deleted: 7 },
    { path: "notebooks/a.ipynb", edits: 1, added: null, deleted: null },
  ],
};

function fileRow(path: string): HTMLElement {
  return screen.getByText(path).closest("li") as HTMLElement;
}

describe("StepDetail files touched", () => {
  it("shows each file's added and deleted lines", () => {
    render(<StepDetail step={{ number: 5, title: "API", phase: "Green", phaseSince: "2026-10-26T12:00:00Z" }} detail={detail} nowMs={0} />);

    const row = fileRow("src/api.py");
    expect(row.querySelector(".add")?.textContent).toBe("+42");
    expect(row.querySelector(".del")?.textContent).toBe("−7");
  });

  it("shows a file's lines as unknown when they couldn't be read, never as zero", () => {
    render(<StepDetail step={{ number: 5, title: "API", phase: "Green", phaseSince: "2026-10-26T12:00:00Z" }} detail={detail} nowMs={0} />);

    const row = fileRow("notebooks/a.ipynb");
    expect(row.querySelector(".add")).toBeNull();
    expect(row.querySelector("[aria-label='unknown']")).not.toBeNull();
  });
});

describe("StepDetail in a Spec Job", () => {
  it("shows its merge into the integration branch with the merge SHA and how long ago", () => {
    render(
      <StepDetail
        step={{ number: 5, title: "API", phase: "Merged", phaseSince: "2026-10-26T12:00:00Z" }}
        detail={{ ...detail, merge: { sha: "a41c9e2", at: "2026-10-26T12:00:00Z" } }}
        nowMs={Date.parse("2026-10-26T12:31:00Z")} inSpecJob integrationBranch="spec/order-export"
      />,
    );

    expect(screen.getByText(/Merged into/).textContent?.trim()).toBe("Merged into spec/order-export · a41c9e2 · 31m ago");
  });
});
