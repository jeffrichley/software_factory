/** Vocabulary the design system renders; mirrors GLOSSARY.md. */

export type SessionState = "Working" | "Needs you" | "Done" | "Stale";

/** The kind of a Tracked session running no skill that the skill table gives a kind (Job or planning). */
export const AD_HOC = "ad hoc";

/** Visual tone of a state; "done" is Done and unseen. */
export type Tone = "needs" | "working" | "done" | "done-seen" | "stale";

export const PHASES = ["Exploring", "Red", "Green", "Refactor", "Reviewing", "Committed", "Merged"] as const;
export type Phase = (typeof PHASES)[number];
