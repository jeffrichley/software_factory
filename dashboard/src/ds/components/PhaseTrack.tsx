import { PHASES, type Phase } from "../types";
import { UnknownPhase } from "./Unknown";

const slug = (p: Phase) => p.toLowerCase();

/** Seven-pip track of a Step's Phase; an unknown Phase shows the placeholder, never a guess. */
export function PhaseTrack({ phase, compact }: { phase: Phase | null; compact?: boolean }) {
  if (!phase) return compact ? <span className="tag tag-unknown">Phase unknown</span> : <UnknownPhase />;
  const idx = PHASES.indexOf(phase);
  return (
    <ol className={`ptrack${compact ? " compact" : ""}`} aria-label={`Phase ${idx + 1} of ${PHASES.length}: ${phase}`}>
      {PHASES.map((p, i) => (
        <li key={p} className={`${i < idx ? "past" : i === idx ? "cur" : ""} ph-${slug(p)}`} aria-current={i === idx ? "step" : undefined}>
          <span className="pip" />
          <span className="pl">{p}</span>
        </li>
      ))}
    </ol>
  );
}

export function PhaseName({ phase }: { phase: Phase }) {
  return <span className={`phase-name ph-${slug(phase)}`}>{phase}</span>;
}
