import { useCallback, useEffect, useMemo, useState } from "react";
import { Background, MarkerType, ReactFlow, ReactFlowProvider, useNodesState, useReactFlow, Controls, MiniMap, type Edge, type Node } from "@xyflow/react";
import { Maximize2, RotateCcw } from "lucide-react";
import type { GraphData, GraphEdge, GraphNode } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { inr, inrCompact } from "@/lib/format";
import { NEUTRAL_NODE, SEVERITY } from "@/lib/tokens";
import { AccountNode, type AccountNodeData } from "./AccountNode";
import { FlowEdge, type FlowEdgeData } from "./FlowEdge";
import { computeLayout, edgeWidth, parallelOffsets } from "./layout";

const nodeTypes = { account: AccountNode };
const edgeTypes = { flow: FlowEdge };
const nodeColor = (n: GraphNode) => (n.has_alert && n.severity ? SEVERITY[n.severity].hex : NEUTRAL_NODE);

interface Props {
  graph: GraphData; selectedId?: string | null; onSelect?: (id: string | null) => void; interactive?: boolean; showLabels?: boolean;
  onHoverEdge?: (e: GraphEdge | null) => void; onHoverNode?: (n: GraphNode | null) => void; minimap?: boolean;
}

function Inner({ graph, selectedId, onSelect, interactive = true, showLabels, onHoverEdge, onHoverNode, minimap }: Props) {
  const layout = useMemo(() => computeLayout(graph), [graph]);
  const { fitView } = useReactFlow();
  const [hover, setHover] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph]);
  const nbr = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of graph.edges) { (m.get(e.source) ?? m.set(e.source, new Set()).get(e.source)!).add(e.target); (m.get(e.target) ?? m.set(e.target, new Set()).get(e.target)!).add(e.source); }
    return m;
  }, [graph]);
  const focus = selectedId ?? hover;

  useEffect(() => {
    setNodes(graph.nodes.map((n) => {
      const p = layout.get(n.id) ?? { x: 0, y: 0, r: 10 };
      const data: AccountNodeData = { label: n.id, r: p.r, color: nodeColor(n), center: n.is_center, selected: false, dim: false, showLabel: false, alert: n.has_alert };
      return { id: n.id, type: "account", position: { x: p.x - p.r, y: p.y - p.r }, data, draggable: interactive, selectable: false };
    }));
    const t = setTimeout(() => void fitView({ padding: 0.18, duration: 250 }), 30);
    return () => clearTimeout(t);
  }, [graph, layout, interactive, setNodes, fitView]);

  useEffect(() => {
    const many = graph.nodes.length > 28;
    setNodes((ns) => ns.map((nd) => {
      const n = byId.get(nd.id)!;
      const near = focus ? nd.id === focus || nbr.get(focus)?.has(nd.id) : true;
      const data: AccountNodeData = { ...(nd.data as AccountNodeData), selected: nd.id === selectedId, dim: !near,
        showLabel: showLabels !== false && (!many || n.is_center || n.has_alert || nd.id === focus || (!!focus && !!nbr.get(focus)?.has(nd.id))) };
      return { ...nd, data };
    }));
  }, [focus, selectedId, graph, byId, nbr, showLabels, setNodes]);

  const edges: Edge[] = useMemo(() => {
    const off = parallelOffsets(graph.edges);
    const few = graph.edges.length <= 40;
    return graph.edges.map((e) => {
      const incident = !!focus && (e.source === focus || e.target === focus);
      const color = incident ? "#22d3ee" : e.flagged ? "#fbbf24" : "#3f5078";
      const sr = layout.get(e.source)?.r ?? 10, tr = layout.get(e.target)?.r ?? 10;
      const label = interactive && (incident || (few && graph.mode === "aggregated")) ? (e.aggregated ? `×${e.txn_count} · ${inrCompact(e.total_amount_inr)}` : inrCompact(e.total_amount_inr)) : undefined;
      const data: FlowEdgeData = { offset: off.get(e.id) ?? 0, width: edgeWidth(e.aggregated ? e.total_amount_inr / Math.sqrt(e.txn_count) : e.total_amount_inr), color, dim: !!focus && !incident, emphasis: incident || e.flagged, label, sR: sr, tR: tr };
      return { id: e.id, source: e.source, target: e.target, type: "flow", data, markerEnd: { type: MarkerType.ArrowClosed, color, width: 12, height: 12 }, zIndex: incident ? 10 : 0 };
    });
  }, [graph, focus, layout, interactive]);

  const edgeById = useMemo(() => new Map(graph.edges.map((e) => [e.id, e])), [graph]);
  const reset = useCallback(() => { onSelect?.(null); void fitView({ padding: 0.18, duration: 300 }); }, [fitView, onSelect]);

  return (
    <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
      minZoom={0.15} maxZoom={3} nodesConnectable={false} elementsSelectable={false}
      nodesDraggable={interactive} panOnDrag={interactive} zoomOnScroll={interactive} zoomOnPinch={interactive} zoomOnDoubleClick={false} preventScrolling={interactive}
      onNodeClick={(_, n) => onSelect?.(n.id)} onPaneClick={() => onSelect?.(null)}
      onNodeMouseEnter={(_, n) => { setHover(n.id); onHoverNode?.(byId.get(n.id) ?? null); }} onNodeMouseLeave={() => { setHover(null); onHoverNode?.(null); }}
      onEdgeMouseEnter={(_, e) => onHoverEdge?.(edgeById.get(e.id) ?? null)} onEdgeMouseLeave={() => onHoverEdge?.(null)}>
      <Background gap={28} size={1} color="#16223a" />
      {interactive && <Controls showInteractive={false} position="bottom-right" />}
      {interactive && minimap && <MiniMap pannable zoomable position="top-right" nodeColor={(n) => (n.data as AccountNodeData).color} maskColor="rgba(7,11,20,.7)" style={{ width: 130, height: 90 }} />}
      {interactive && (
        <div className="absolute left-3 top-3 z-10 flex gap-1.5">
          <Button size="sm" onClick={() => void fitView({ padding: 0.18, duration: 300 })} aria-label="Fit to view"><Maximize2 className="size-3.5" />Fit</Button>
          <Button size="sm" onClick={reset} aria-label="Reset view and selection"><RotateCcw className="size-3.5" />Reset</Button>
        </div>
      )}
    </ReactFlow>
  );
}

export function NetworkGraph(p: Props) {
  const key = useMemo(() => `${p.graph.mode}|${p.graph.center}|${p.graph.nodes.map((n) => n.id).join(",")}|${p.graph.edges.length}`, [p.graph]);
  return (
    <ReactFlowProvider>
      <div className="size-full" aria-label="Transaction network graph" role="application"><Inner key={key} {...p} /></div>
    </ReactFlowProvider>
  );
}

export const edgeSummary = (e: GraphEdge) => (e.aggregated ? `${e.txn_count} txn${e.txn_count > 1 ? "s" : ""} · ${inr(e.total_amount_inr)}` : inr(e.total_amount_inr));
