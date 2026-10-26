import dagre from "@dagrejs/dagre";

/**
 * The one graph grammar (Spec Ticket DAGs, Maps, to-tickets output):
 * solid = resolved, dashed grey = waiting, dashed red = blocking,
 * dashed blue + FRONTIER = takeable now.
 */

export type EdgeKind = "resolved" | "waiting" | "blocking";

export interface GraphItem {
  id: string;
  deps: string[];
  /** Merged Step, closed Decision ticket. */
  resolved: boolean;
  /** Already taken by a session (Maps); claimed items are never frontier. */
  claimed?: boolean;
  blockedBy?: string;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  kind: EdgeKind;
}

export function classifyGraph(items: GraphItem[]): { edges: GraphEdge[]; frontier: string[] } {
  const byId = new Map(items.map((n) => [n.id, n]));
  const isResolved = (id: string) => byId.get(id)?.resolved ?? false;
  const edges = items.flatMap((n) =>
    n.deps.map((from): GraphEdge => ({
      id: `${from}->${n.id}`,
      from,
      to: n.id,
      kind: n.blockedBy === from ? "blocking" : isResolved(from) ? "resolved" : "waiting",
    })),
  );
  const frontier = items.filter((n) => !n.resolved && !n.claimed && n.deps.every(isResolved)).map((n) => n.id);
  return { edges, frontier };
}

/** Column and row gaps from variant E's graph. */
const COL_GAP = 64;
const ROW_GAP = 20;

/** Left→right layout; returns each item's top-left corner. */
export function layoutGraph(
  items: GraphItem[],
  size: { width: number; height: number },
): Record<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", ranksep: COL_GAP, nodesep: ROW_GAP, marginx: 0, marginy: 0 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of items) g.setNode(n.id, { width: size.width, height: size.height });
  for (const n of items) for (const d of n.deps) g.setEdge(d, n.id);
  dagre.layout(g);
  return Object.fromEntries(
    items.map((n) => {
      const p = g.node(n.id);
      return [n.id, { x: p.x - size.width / 2, y: p.y - size.height / 2 }];
    }),
  );
}
