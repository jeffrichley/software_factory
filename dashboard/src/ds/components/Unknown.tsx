import { formatDuration } from "../format";
import { Icon } from "./Icon";
import { Tag } from "./Tag";

/** The one way to show a value the Factory does not know: never guessed. */
export function Unknown() {
  return <span className="unknown" aria-label="unknown">—</span>;
}

/** Placeholder where a Phase track would be when no Phase signal has arrived. */
export function UnknownPhase({ detail }: { detail?: string }) {
  return (
    <p className="unknown-phase">
      <Icon name="question" />
      <span>
        <b>Phase unknown</b>
        {detail ? ` — ${detail}` : null}
      </span>
    </p>
  );
}

export function UnknownPhaseTag() {
  return <Tag tone="unknown">Phase unknown</Tag>;
}

/** Why a Stale session's state can't be trusted; on a silent Machine, when it was last seen. */
export function StaleNote({ reason, machine, silentForMs }: { reason: string; machine?: string; silentForMs?: number }) {
  return (
    <p className="stale-note">
      <Icon name="clock" />
      <span>
        <b>Stale</b> · {reason}
        {machine && silentForMs !== undefined ? ` — ${machine} last seen ${formatDuration(silentForMs)} ago` : null}
      </span>
    </p>
  );
}
