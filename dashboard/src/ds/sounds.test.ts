import { describe, expect, it } from "vitest";
import { newSounds } from "./sounds";

const sound = (id: number, kind: "needs_you" | "done" = "needs_you") => ({ id, sound: kind });

describe("newSounds", () => {
  it("plays nothing already in the state when the page opens", () => {
    expect(newSounds([sound(3), sound(4, "done")], undefined)).toEqual({ play: [], heard: 4 });
    expect(newSounds([], undefined)).toEqual({ play: [], heard: 0 });
  });

  it("plays each sound the server adds once, in order", () => {
    const first = newSounds([sound(3), sound(4, "done")], 3);
    expect(first).toEqual({ play: [sound(4, "done")], heard: 4 });

    expect(newSounds([sound(3), sound(4, "done")], first.heard)).toEqual({ play: [], heard: 4 });
    expect(newSounds([sound(4, "done"), sound(5), sound(6, "done")], 4).play).toEqual([sound(5), sound(6, "done")]);
  });
});
