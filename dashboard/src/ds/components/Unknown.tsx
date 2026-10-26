import { Icon } from "./Icon";

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
  return <span className="tag tag-unknown">Phase unknown</span>;
}

/** Why a Stale session's state can't be trusted. */
export function StaleNote({ reason }: { reason: string }) {
  return (
    <p className="stale-note">
      <Icon name="clock" />
      <b>Stale</b> · {reason}
    </p>
  );
}
