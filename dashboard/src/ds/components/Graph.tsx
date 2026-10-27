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
import { type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { formatDuration, phaseClass } from "../format";
import { classifyGraph, fitZoom, layoutGraph, type EdgeKind, type GraphItem } from "../graph";
import { PENDING, type StepPhase } from "../types";
import { PhaseTrack } from "./PhaseTrack";
import { Tag } from "./Tag";

/** What a node shows, by kind: Spec Steps, Map Decision tickets, to-tickets output. */
export type GraphNodeBody =
  | { kind: "step"; ticket: string; phase: StepPhase; phaseForMs?: number }
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
const FOG = { width: 200, height: 100, gap: 64, rowGap: 12 };
/** Space around the graph inside its frame. */
const PAD = 24;

function Badge({ text, cls = "" }: { text: string; cls?: string }) {
  return <span className={`gbadge ${cls}`}>{text}</span>;
}

function StepBody({ b, d }: { b: Extract<GraphNodeBody, { kind: "step" }>; d: NodeData }) {
  const pending = b.phase === PENDING;
  return (
    <>
      <span className="gt one">{b.ticket}</span>
      <span className="grow">
        <span className={`np ${phaseClass(b.phase === PENDING ? null : b.phase)}`}>
          {b.phase ? b.phase : "Phase unknown"}
          {b.phase && !pending && b.phase !== "Merged" && b.phaseForMs !== undefined ? ` · ${formatDuration(b.phaseForMs)}` : ""}
        </span>
        <span className="spacer" />
        {d.blocked ? <Badge text="BLOCKED" cls="blk" /> : d.frontier ? <Badge text="FRONTIER" cls="fr" /> : null}
      </span>
      {b.phase && b.phase !== PENDING ? <PhaseTrack phase={b.phase} compact /> : null}
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
  const cls = ["gnode", b.kind, data.frontier && "frontier", data.needs && "needs", data.muted && "muted"].filter(Boolean).join(" ");
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
    <div className="gfog-node" style={{ width: FOG.width, height: FOG.height }} role="img" aria-label={`Not yet specified: ${data.text}`}>
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
  /** Shrink a graph wider than its box to fit it; otherwise it is drawn 1:1 and scrolls sideways. */
  fit?: boolean;
}

/** The width of an element's content box, kept current. */
function useBoxWidth<E extends HTMLElement>(): [RefObject<E | null>, number] {
  const ref = useRef<E>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

/** The one graph style: left→right; solid = resolved, dashed grey = waiting, dashed red = blocking, dashed blue + FRONTIER = takeable now. */
export function GraphView({ items, fog = [], selectedId, onSelect, label, legend = true, fit = false }: GraphViewProps) {
  const [box, boxWidth] = useBoxWidth<HTMLDivElement>();
  const { nodes, edges, width, height } = useMemo(() => {
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
    const fogH = fog.length * (FOG.height + FOG.rowGap);
    const top = Math.max(0, (maxY - fogH) / 2);
    fog.forEach((text, i) =>
      nodes.push({ id: `fog-${i}`, type: "fog", position: { x: maxX + FOG.gap, y: top + i * (FOG.height + FOG.rowGap) }, data: { text, first: i === 0 } satisfies FogData, selectable: false }),
    );
    const edges: Edge[] = ge.map((e) => ({ id: e.id, source: e.from, target: e.to, type: "factory", data: { kind: e.kind } }));
    const width = (fog.length ? maxX + FOG.gap + FOG.width : maxX) + 2 * PAD;
    return { nodes, edges, width, height: Math.max(maxY, fogH) + 2 * PAD };
  }, [items, fog, selectedId]);
  const zoom = fit ? fitZoom(width, boxWidth) : 1;

  return (
    <div className="fgraph" role="group" aria-label={label}>
      {/* Drawn 1:1 like variant E; a wide graph scrolls sideways inside its box unless fitted to it. */}
      <div className="fgraph-scroll" ref={box}>
        <div className="fgraph-canvas" style={{ width: width * zoom, height: height * zoom }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            viewport={{ x: PAD * zoom, y: PAD * zoom, zoom }}
            minZoom={0.05}
            panOnDrag={false}
            zoomOnPinch={false}
            zoomOnDoubleClick={false}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={!!onSelect}
            zoomOnScroll={false}
            preventScrolling={false}
            proOptions={{ hideAttribution: true }}
            onNodeClick={(_, n) => n.type === "factory" && onSelect?.(n.id)}
          />
        </div>
      </div>
      {legend ? (
        <div className="glegend">
          <span><span className="lg-line" />resolved</span>
          <span><span className="lg-line waiting" />waiting on dependency</span>
          <span><span className="lg-line blocking" />blocking</span>
          <span><Tag tone="frontier">Frontier</Tag>takeable now</span>
        </div>
      ) : null}
    </div>
  );
}
