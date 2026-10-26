import { formatDuration } from "../format";

export interface MachinePillProps {
  name: string;
  sessions: number;
  /** Set when the Machine has gone silent: ms since its last event. */
  silentForMs?: number;
  hidden?: boolean;
  onToggle?: () => void;
}

export function MachinePill({ name, sessions, silentForMs, hidden, onToggle }: MachinePillProps) {
  const silent = silentForMs !== undefined;
  const meta = silent ? `last seen ${formatDuration(silentForMs)}` : `${sessions} sessions`;
  return (
    <button
      type="button"
      className={`mpill${silent ? " silent" : ""}${hidden ? " off" : ""}`}
      aria-pressed={!hidden}
      title={`${hidden ? "Show" : "Hide"} ${name}`}
      aria-label={`Machine ${name}: ${hidden ? "hidden" : "shown"}; ${silent ? `silent, ${meta} ago` : `reporting, ${meta}`}`}
      onClick={onToggle}
    >
      <span className="mdot" aria-hidden="true" />
      <span className="mono">{name}</span>
      <span className="mmeta">{meta}</span>
    </button>
  );
}
