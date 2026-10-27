import { describe, expect, it } from "vitest";
import { currentItem, diffBlocks, phaseChange, struggleLabels } from "./stepDetail";

describe("struggleLabels", () => {
  it("says nothing for a Step that isn't struggling", () => {
    expect(struggleLabels(null)).toEqual([]);
  });

  it("names each reason: failures in a row, the files churned, and the silence", () => {
    expect(struggleLabels({ failures: 4, churn: ["src/api.py", "src/db.py"], silentForS: 754 })).toEqual([
      "Struggling · 4 test failures",
      "Churn · src/api.py, src/db.py",
      "Silence · 12m",
    ]);
  });

  it("leaves out the reasons that don't hold", () => {
    expect(struggleLabels({ failures: null, churn: ["src/api.py"], silentForS: null })).toEqual(["Churn · src/api.py"]);
  });
});

describe("diffBlocks", () => {
  it("splits five blocks between added and deleted lines, the rest empty", () => {
    expect(diffBlocks(72, 8)).toEqual(["a", "a", "a", "a", "d"]);
    expect(diffBlocks(10, 10)).toEqual(["a", "a", "a", "d", "d"]);
    expect(diffBlocks(3, 0)).toEqual(["a", "a", "a", "a", "a"]);
  });

  it("is empty for a commit that changed no lines", () => {
    expect(diffBlocks(0, 0)).toEqual(["", "", "", "", ""]);
  });
});

describe("phaseChange", () => {
  it("reads as from → to, naming an unknown Phase as such", () => {
    expect(phaseChange({ at: "", from: "Exploring", to: "Red" })).toBe("Exploring → Red");
    expect(phaseChange({ at: "", from: null, to: "Exploring" })).toBe("Phase unknown → Exploring");
    expect(phaseChange({ at: "", from: "Pending", to: null })).toBe("Pending → Phase unknown");
  });
});

describe("currentItem", () => {
  it("is the item in progress, else the first not done, else none", () => {
    expect(currentItem([{ text: "a", status: "completed" }, { text: "b", status: "pending" }, { text: "c", status: "in_progress" }])).toBe(2);
    expect(currentItem([{ text: "a", status: "completed" }, { text: "b", status: "pending" }])).toBe(1);
    expect(currentItem([{ text: "a", status: "completed" }])).toBe(-1);
  });
});
