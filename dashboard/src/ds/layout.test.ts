// Guards for layout jsdom can't measure: what keeps a state badge whole at narrow widths, read from the stylesheet.
import { describe, expect, it } from "vitest";
import css from "./components.css?raw";

/** The declarations of the top-level rule with exactly this selector (first one), as property → value. */
function rule(selector: string): Record<string, string> {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\>]/g, "\\$&");
  const m = new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(css);
  if (!m) throw new Error(`no rule for ${selector}`);
  return Object.fromEntries(
    m[1].split(";").map((d) => d.split(":").map((x) => x.trim())).filter(([k, v]) => k && v).map(([k, v]) => [k, v]),
  );
}

describe("state badges never clip at narrow widths", () => {
  it("a badge keeps its text on one line and is never cut or ellipsized", () => {
    const badge = rule(".state");
    expect(badge["white-space"]).toBe("nowrap");
    for (const clipping of ["overflow", "text-overflow", "max-width", "width"]) expect(badge[clipping]).toBeUndefined();
  });

  it("the session header's meta row wraps the badge to its own line instead of squeezing it", () => {
    const meta = rule(".sd-meta");
    expect(meta["flex-wrap"]).toBe("wrap");
    expect(meta.overflow).toBeUndefined();
  });

  it("an inbox card's header wraps its reason and waiting time instead of clipping them under the card's rounded edge", () => {
    expect(rule(".ncard > header")["flex-wrap"]).toBe("wrap");
  });
});
