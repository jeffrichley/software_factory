import { motion as m } from "framer-motion";
import { useLayoutEffect, useRef, useState } from "react";
import { phaseClass, repoName, stateLook } from "../format";
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
  /** ms a Working session has had no events: its chip is dimmed. */
  quietMs?: number;
  selected?: boolean;
  onOpen?: () => void;
}

/** Flow-strip chip for one Step or planning session: coloured by state, pulses when it Needs you, glides between Phases. */
export function StateChip(p: StateChipProps) {
  const { tone, label: stateLabel } = stateLook(p.state, p.seen, undefined, p.quietMs);
  const [tip, setTip] = useState<DOMRect | null>(null);
  const tipRef = useRef<HTMLSpanElement>(null);
  const chipRef = useRef<HTMLButtonElement>(null);
  // Keep the tooltip inside the viewport, using its real width.
  useLayoutEffect(() => {
    const el = tipRef.current;
    if (!tip || !el) return;
    el.style.left = `${Math.max(8, Math.min(window.innerWidth - el.offsetWidth - 8, tip.left))}px`;
    el.style.top = `${tip.bottom + 8}px`;
  }, [tip]);
  // Cells clip their chips; while a chip glides to a new cell, let it show.
  const gliding = (el: HTMLElement, on: boolean) => {
    el.classList.toggle("gliding", on);
    el.closest(".flow")?.classList.toggle("animating", on);
  };
  const stateTxt = stateLabel + (p.staleReason ? ` · ${p.staleReason}` : "") + (p.blocked ? " · blocked" : "");
  const phaseTxt = p.phase === "planning" ? `${p.groupName ?? "Planning"} session` : p.phase ? `Phase: ${p.phase}` : "Phase unknown";
  return (
    <>
      <m.button
        type="button"
        layout="position"
        layoutId={p.id}
        transition={glide}
        ref={chipRef}
        onLayoutAnimationStart={() => chipRef.current && gliding(chipRef.current, true)}
        onLayoutAnimationComplete={() => chipRef.current && gliding(chipRef.current, false)}
        className={`fchip fs-${tone} ${phaseClass(p.phase)}${p.quietMs !== undefined ? " quiet" : ""}${p.selected ? " sel" : ""}`}
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
        <span className="ftip" role="tooltip" ref={tipRef}>
          <span className="ft-tt">{p.name}</span>
          {p.groupName ? <span className="ft-tg">{p.groupName}</span> : null}
          <span className="ft-tp">{phaseTxt}</span>
          <span className="ft-ts">{stateTxt}</span>
          <span className="ft-tm">{`${p.machine} · ${repoName(p.repo)}`}</span>
        </span>
      ) : null}
    </>
  );
}
