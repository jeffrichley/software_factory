import { motion as m } from "framer-motion";
import { useState } from "react";
import { stateLook } from "../format";
import { glide } from "../motion";
import type { Phase, SessionState } from "../types";
import { Icon, type IconName } from "./Icon";

export interface StateChipProps {
  /** Stable across renders and columns: the chip glides when its column changes. */
  id: string;
  label: string;
  /** Full name for the tooltip and screen readers. */
  name: string;
  state: SessionState;
  seen?: boolean;
  /** A Step's Phase (null = unknown), or "planning" for a planning / ad hoc session. */
  phase: Phase | null | "planning";
  /** Spec initials shown on each of a Spec Job's Step chips. */
  group?: string;
  groupName?: string;
  planIcon?: IconName;
  machine: string;
  repo: string;
  blocked?: boolean;
  staleReason?: string;
  selected?: boolean;
  onOpen?: () => void;
}

function phaseClass(phase: StateChipProps["phase"]) {
  if (phase === "planning") return "fplan";
  return phase ? `ph-${phase.toLowerCase()}` : "ph-unknown";
}

/** Flow-strip chip for one Step or planning session: coloured by state, pulses when it Needs you, glides between Phases. */
export function StateChip(p: StateChipProps) {
  const { tone, label: stateLabel } = stateLook(p.state, p.seen);
  const [tip, setTip] = useState<DOMRect | null>(null);
  const stateTxt = stateLabel + (p.staleReason ? ` · ${p.staleReason}` : "") + (p.blocked ? " · blocked" : "");
  const phaseTxt = p.phase === "planning" ? `${p.groupName ?? "Planning"} session` : p.phase ? `Phase: ${p.phase}` : "Phase unknown";
  return (
    <>
      <m.button
        type="button"
        layout="position"
        layoutId={p.id}
        transition={glide}
        className={`fchip fs-${tone} ${phaseClass(p.phase)}${p.selected ? " sel" : ""}`}
        aria-label={`${p.name} — ${phaseTxt}, ${stateTxt}, ${p.machine}`}
        onClick={p.onOpen}
        onMouseEnter={(e) => setTip(e.currentTarget.getBoundingClientRect())}
        onMouseLeave={() => setTip(null)}
        onFocus={(e) => setTip(e.currentTarget.getBoundingClientRect())}
        onBlur={() => setTip(null)}
      >
        <span className={`fdot${tone === "needs" ? " pulse" : ""}`} aria-hidden="true" />
        {p.group ? <span className="fgrp" aria-hidden="true">{p.group}</span> : null}
        {p.phase === "planning" ? <Icon name={p.planIcon ?? "terminal"} /> : null}
        <span className="fl">{p.label}</span>
      </m.button>
      {tip ? (
        <span className="ftip" role="tooltip" style={{ left: Math.max(8, Math.min(window.innerWidth - 328, tip.left)), top: tip.bottom + 8 }}>
          <span className="ft-tt">{p.name}</span>
          {p.groupName ? <span className="ft-tg">{p.groupName}</span> : null}
          <span className="ft-tp">{phaseTxt}</span>
          <span className="ft-ts">{stateTxt}</span>
          <span className="ft-tm">{`${p.machine} · ${p.repo}`}</span>
        </span>
      ) : null}
    </>
  );
}
