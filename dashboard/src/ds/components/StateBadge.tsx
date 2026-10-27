import { stateLook, type StateLook } from "../format";
import type { SessionState } from "../types";
import { Icon, type IconName } from "./Icon";

const ICON = { needs: "alert", working: "work", done: "check", "done-seen": "check", stale: "clock" } as const satisfies Record<string, IconName>;

export interface StateBadgeProps {
  state: SessionState;
  seen?: boolean;
  staleReason?: string;
  /** Working only: ms without events, shown as "Working · quiet 23m". */
  quietMs?: number;
  /** Pass when the caller already has it (e.g. for a row's label), so it isn't worked out twice. */
  look?: StateLook;
}

export function StateBadge({ state, seen, staleReason, quietMs, look }: StateBadgeProps) {
  const { tone, label } = look ?? stateLook(state, seen, staleReason, quietMs);
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
