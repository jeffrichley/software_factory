import type { ReactNode } from "react";
import { formatDuration } from "../format";

export interface MachinePillProps {
  name: string;
  sessions: number;
  /** Set when the Machine has gone silent: ms since its last event. */
  silentForMs?: number;
  hidden?: boolean;
  /** Without it the pill only shows the Machine: no button, nothing to click. */
  onToggle?: () => void;
}

export function MachinePill({ name, sessions, silentForMs, hidden, onToggle }: MachinePillProps) {
  const silent = silentForMs !== undefined;
  const meta = silent ? `last seen ${formatDuration(silentForMs)}` : `${sessions} sessions`;
  const status = silent ? `silent, ${meta} ago` : `reporting, ${meta}`;
  const body = (
    <>
      <span className="mdot" aria-hidden="true" />
      <span className="mono">{name}</span>
      <span className="mmeta">{meta}</span>
    </>
  );
  if (!onToggle) {
    return <span className={`mpill inert${silent ? " silent" : ""}`} aria-label={`Machine ${name}: ${status}`}>{body}</span>;
  }
  return (
    <button
      type="button"
      className={`mpill${silent ? " silent" : ""}${hidden ? " off" : ""}`}
      aria-pressed={!hidden}
      title={`${hidden ? "Show" : "Hide"} ${name}`}
      aria-label={`Machine ${name}: ${hidden ? "hidden" : "shown"}; ${status}`}
      onClick={onToggle}
    >
      {body}
    </button>
  );
}

/** The header's row of Machine pills, one per Machine. */
export function MachinePills({ children }: { children?: ReactNode }) {
  return <div className="mpills">{children}</div>;
}
