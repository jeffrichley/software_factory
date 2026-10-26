import {
  BaseEdge,
  getBezierPath,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/base.css";
import { useMemo } from "react";
import { formatDuration } from "../format";
import { classifyGraph, layoutGraph, type EdgeKind, type GraphItem } from "../graph";
import type { Phase } from "../types";
import { PhaseTrack } from "./PhaseTrack";

/** What a node shows, by kind: Spec Steps, Map Decision tickets, to-tickets output. */
export type GraphNodeBody =
  | { kind: "step"; ticket: string; phase: Phase | null; phaseForMs?: number }
  | {
      kind: "decision";
      name: string;
      type: string;
      mode: string;
      status: { state: "open" } | { state: "closed"; gist: string } | { state: "claimed"; by: string };
      needs?: boolean;
      blockedByName?: string;
    }
  | { kind: "ticket"; name: string };

export type GraphNodeInput = GraphItem & { body: GraphNodeBody; muted?: boolean };

type NodeData = { body: GraphNodeBody; frontier: boolean; blocked: boolean; muted: boolean; needs: boolean };
type FogData = { text: string; first: boolean };

const SIZE: Record<GraphNodeBody["kind"], { width: number; height: number }> = {
  step: { width: 232, height: 88 },
  decision: { width: 280, height: 140 },
  ticket: { width: 220, height: 72 },
};
const FOG = { width: 200, height: 100, gap: 64 };

function Badge({ text, cls = "" }: { text: string; cls?: string }) {
  return <span className={`gbadge ${cls}`}>{text}</span>;
}

function StepBody({ b, d }: { b: Extract<GraphNodeBody, { kind: "step" }>; d: NodeData }) {
  return (
    <>
      <span className="gt one">{b.ticket}</span>
      <span className="grow">
        <span className={`np${b.phase ? ` ph-${b.phase.toLowerCase()}` : ""}`}>
          {b.phase ? b.phase : "Phase unknown"}
          {b.phase && b.phase !== "Merged" && b.phaseForMs !== undefined ? ` · ${formatDuration(b.phaseForMs)}` : ""}
        </span>
        <span className="spacer" />
        {d.blocked ? <Badge text="BLOCKED" cls="blk" /> : d.frontier ? <Badge text="FRONTIER" cls="fr" /> : null}
      </span>
      {b.phase ? <PhaseTrack phase={b.phase} compact /> : null}
    </>
  );
}

function DecisionBody({ b, d }: { b: Extract<GraphNodeBody, { kind: "decision" }>; d: NodeData }) {
  const status = b.status.state === "claimed" ? `claimed by ${b.status.by}` : b.status.state;
  return (
    <>
      <span className="gt">{b.name}</span>
      <span className="grow">
        <Badge text={b.type.toUpperCase()} />
        <Badge text={b.mode} cls="mode" />
        <span className="spacer" />
        {d.needs ? <Badge text="NEEDS YOU" cls="needs" /> : d.blocked ? <Badge text="BLOCKED" cls="blk" /> : d.frontier ? <Badge text="FRONTIER" cls="fr" /> : null}
      </span>
      <span className={`gs truncate${b.status.state === "claimed" ? " claimed" : ""}`}>{status}</span>
      {b.status.state === "closed" ? (
        <span className="gs2 truncate">{b.status.gist}</span>
      ) : d.blocked && b.blockedByName ? (
        <span className="gs2 blk truncate">blocked by {b.blockedByName}</span>
      ) : d.frontier ? (
        <span className="gs2 fr">takeable now</span>
      ) : null}
    </>
  );
}

function TicketBody({ b, d }: { b: Extract<GraphNodeBody, { kind: "ticket" }>; d: NodeData }) {
  return (
    <>
      <span className="gt one">{b.name}</span>
      <span className="grow">
        <Badge text="NOT STARTED" cls="ns" />
        <span className="spacer" />
        {d.frontier ? <Badge text="FRONTIER" cls="fr" /> : null}
      </span>
    </>
  );
}

function FactoryNode({ data }: NodeProps<Node<NodeData>>) {
  const b = data.body;
  const cls = ["gnode", data.frontier && "frontier", data.needs && "needs", data.muted && "muted"].filter(Boolean).join(" ");
  return (
    <div className={cls} style={SIZE[b.kind]}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      {b.kind === "step" ? <StepBody b={b} d={data} /> : b.kind === "decision" ? <DecisionBody b={b} d={data} /> : <TicketBody b={b} d={data} />}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

function FogNode({ data }: NodeProps<Node<FogData>>) {
  return (
    <div style={{ width: FOG.width, height: FOG.height, display: "grid", gridTemplateRows: "auto 1fr" }} role="img" aria-label={`Not yet specified: ${data.text}`}>
      <span className="gfog-h">{data.first ? "NOT YET SPECIFIED" : " "}</span>
      <div className="gfog">
        <span>{data.text}</span>
      </div>
    </div>
  );
}

function FactoryEdge(p: EdgeProps<Edge<{ kind: EdgeKind }>>) {
  const kind = p.data?.kind ?? "waiting";
  const tx = p.targetX - 6;
  const [path] = getBezierPath({ sourceX: p.sourceX, sourceY: p.sourceY, sourcePosition: p.sourcePosition, targetX: tx, targetY: p.targetY, targetPosition: p.targetPosition });
  return (
    <>
      <BaseEdge id={p.id} path={path} className={`gedge ${kind}`} />
      <path className={`garrow ${kind}`} d={`M${tx - 2} ${p.targetY - 4.5} L${tx + 6} ${p.targetY} L${tx - 2} ${p.targetY + 4.5} z`} />
    </>
  );
}

const nodeTypes = { factory: FactoryNode, fog: FogNode };
const edgeTypes = { factory: FactoryEdge };

export interface GraphViewProps {
  items: GraphNodeInput[];
  /** Map fog: what is not yet specified, drawn past the frontier. */
  fog?: string[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  label: string;
  /** Show the edge legend under the graph. */
  legend?: boolean;
}

/** The one graph style: left→right; solid = resolved, dashed grey = waiting, dashed red = blocking, dashed blue + FRONTIER = takeable now. */
export function GraphView({ items, fog = [], selectedId, onSelect, label, legend = true }: GraphViewProps) {
  const { nodes, edges, height } = useMemo(() => {
    const { edges: ge, frontier } = classifyGraph(items);
    const size = items.reduce((s, n) => ({ width: Math.max(s.width, SIZE[n.body.kind].width), height: Math.max(s.height, SIZE[n.body.kind].height) }), { width: 0, height: 0 });
    const pos = layoutGraph(items, size);
    const fr = new Set(frontier);
    const nodes: Node[] = items.map((n) => ({
      id: n.id,
      type: "factory",
      position: pos[n.id],
      selected: n.id === selectedId,
      data: {
        body: n.body,
        frontier: fr.has(n.id),
        blocked: !!n.blockedBy,
        muted: !!n.muted,
        needs: n.body.kind === "decision" && !!n.body.needs,
      } satisfies NodeData,
    }));
    const maxX = Math.max(0, ...Object.values(pos).map((p) => p.x + size.width));
    const maxY = Math.max(0, ...Object.values(pos).map((p) => p.y + size.height));
    const fogH = fog.length * (FOG.height + 12);
    const top = Math.max(0, (maxY - fogH) / 2);
    fog.forEach((text, i) =>
      nodes.push({ id: `fog-${i}`, type: "fog", position: { x: maxX + FOG.gap, y: top + i * (FOG.height + 12) }, data: { text, first: i === 0 } satisfies FogData, selectable: false }),
    );
    const edges: Edge[] = ge.map((e) => ({ id: e.id, source: e.from, target: e.to, type: "factory", data: { kind: e.kind } }));
    return { nodes, edges, height: Math.max(maxY, fogH) + 48 };
  }, [items, fog, selectedId]);

  return (
    <div className="fgraph" role="group" aria-label={label}>
      <div style={{ height }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.08, maxZoom: 1 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={!!onSelect}
          zoomOnScroll={false}
          preventScrolling={false}
          proOptions={{ hideAttribution: true }}
          onNodeClick={(_, n) => n.type === "factory" && onSelect?.(n.id)}
        />
      </div>
      {legend ? (
        <div className="glegend">
          <span><span className="lg-line" />resolved</span>
          <span><span className="lg-line waiting" />waiting on dependency</span>
          <span><span className="lg-line blocking" />blocking</span>
          <span><span className="tag tag-frontier">Frontier</span>takeable now</span>
        </div>
      ) : null}
    </div>
  );
}
