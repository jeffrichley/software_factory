import type { GraphNodeInput } from "./components/Graph";

/** The session kind of a session running `wayfinder`. */
export const WAYFINDER = "Wayfinder";

/** A Map's Decision ticket as the server polled it. */
export interface DecisionTicketData {
  number: number;
  title: string;
  url: string;
  state: "open" | "closed";
  /** From its `wayfinder:<type>` label; null when it has none. */
  type: string | null;
  /** HITL, AFK or HITL/AFK (a task); null when the type is unknown. */
  mode: string | null;
  /** Who claimed it; open and unassigned = unclaimed. */
  assignees: string[];
  /** The one-line answer the Map's Decisions so far gives it; null when it has none. */
  gist: string | null;
  /** The tickets that block it. */
  blockedBy: number[];
}

/** A wayfinder Map: its Destination, fog (Not yet specified) and Decision tickets (Out of scope left out). */
export interface MapData {
  repo: string;
  number: number;
  title: string;
  url: string;
  destination: string | null;
  fog: string[];
  tickets: DecisionTicketData[];
}

/** What a Wayfinder session is doing on its Map. */
export interface WayfinderData {
  sessionId: string;
  /** The Map's number; null until known. */
  map: number | null;
  /** The Decision ticket being worked; null until the session claims one. */
  ticket: number | null;
  /** The current grilling round's question titles. */
  questions: string[];
  /** Tickets the session created and closed. */
  created: number[];
  closed: number[];
}

export function decisionName(t: { number: number; title: string }): string {
  return `#${t.number} ${t.title}`;
}

/**
 * A Map in the one graph grammar: each Decision ticket depends on the tickets on the Map that block it. A closed ticket
 * is resolved (and muted); a claimed one is never frontier, and is blocked by a blocker still open; an open one waits.
 * `plan`: the ticket this session works, and whether it is waiting on the human.
 */
export function mapGraph(map: MapData, plan: { ticket: number | null; needs: boolean }): GraphNodeInput[] {
  const byNumber = new Map(map.tickets.map((t) => [t.number, t]));
  return map.tickets.map((t) => {
    const closed = t.state === "closed";
    const mine = !closed && plan.ticket === t.number;
    const claimed = !closed && (mine || t.assignees.length > 0);
    const deps = t.blockedBy.filter((n) => byNumber.has(n)).map(String);
    const blocker = claimed ? t.blockedBy.map((n) => byNumber.get(n)).find((b) => b && b.state !== "closed") : undefined;
    return {
      id: String(t.number),
      deps,
      resolved: closed,
      claimed,
      muted: closed,
      ...(blocker ? { blockedBy: String(blocker.number) } : {}),
      body: {
        kind: "decision",
        name: decisionName(t),
        type: t.type ?? "type unknown",
        mode: t.mode ?? "—",
        status: closed
          ? { state: "closed", gist: t.gist ?? "—" }
          : claimed
            ? { state: "claimed", by: mine ? "this session" : t.assignees.join(", ") }
            : { state: "open" },
        needs: mine && plan.needs,
        ...(blocker ? { blockedByName: decisionName(blocker) } : {}),
      },
    };
  });
}
