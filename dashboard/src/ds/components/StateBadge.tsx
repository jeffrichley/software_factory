import { stateLook } from "../format";
import type { SessionState } from "../types";
import { Icon, type IconName } from "./Icon";

const ICON = { needs: "alert", working: "work", done: "check", "done-seen": "check", stale: "clock" } as const satisfies Record<string, IconName>;

export function StateBadge({ state, seen }: { state: SessionState; seen?: boolean }) {
  const { tone, label } = stateLook(state, seen);
  return (
    <span className={`state st-${tone}`}>
      <Icon name={ICON[tone]} />
      {label}
    </span>
  );
}

/** Small state dot; Needs you pulses. */
export function StateDot({ state, seen }: { state: SessionState; seen?: boolean }) {
  const { tone } = stateLook(state, seen);
  return <span className={`dot dot-${tone}${tone === "needs" ? " pulse" : ""}`} aria-hidden="true" />;
}
